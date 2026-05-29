"""
python scripts_slam_pipeline/00_process_videos.py data_workspace/toss_objects/20231113
"""
# %%
import sys
import os
import subprocess
import pathlib

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT_DIR)
os.chdir(ROOT_DIR)

# %%
import pathlib
import click
import shutil
from exiftool import ExifToolHelper
from umi.common.timecode_util import mp4_get_start_datetime


def split_360_video(input_path: pathlib.Path, output_dir: pathlib.Path):
    """
    Extracts front and back lens streams from a GoPro .360 file,
    transcodes them to H.264, and saves them as separate left/right video files.
    """
    print(f"Detected dual-lens video. Splitting into stereo streams...")
    
    left_video_path = output_dir.joinpath("left_video.mp4")
    right_video_path = output_dir.joinpath("right_video.mp4")
    
    cmd_left = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-map', '0:0', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
        str(left_video_path)
    ]
    
    cmd_right = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-map', '0:1', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
        str(right_video_path)
    ]

    print("Extracting Left Camera (Front Lens)...")
    subprocess.run(cmd_left, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("Extracting Right Camera (Back Lens)...")
    subprocess.run(cmd_right, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Stereo split complete!")


# %%
@click.command(help='Session directories. Assumming mp4 videos are in <session_dir>/raw_videos')
@click.argument('session_dir', nargs=-1)
def main(session_dir):
    for session in session_dir:
        session = pathlib.Path(os.path.expanduser(session)).absolute()
        # hardcode subdirs
        input_dir = session.joinpath('raw_videos')
        output_dir = session.joinpath('demos')
        
        # Initialize our tracking flag for the bottom loop
        is_360_mapping = False

        # create raw_videos if don't exist
        if not input_dir.is_dir():
            input_dir.mkdir()
            print(f"{input_dir.name} subdir don't exits! Creating one and moving all mp4 videos inside.")
            # Added .360 to the glob search
            for mp4_path in list(session.glob('**/*.MP4')) + list(session.glob('**/*.mp4')) + list(session.glob('**/*.360')):
                out_path = input_dir.joinpath(mp4_path.name)
                shutil.move(mp4_path, out_path)
        
        # create mapping video if don't exist
        mapping_vid_path = input_dir.joinpath('mapping.mp4')
        if (not mapping_vid_path.exists()) and not(mapping_vid_path.is_symlink()):
            max_size = -1
            max_path = None
            # Added .360 to the glob search
            for mp4_path in list(input_dir.glob('**/*.MP4')) + list(input_dir.glob('**/*.mp4')) + list(input_dir.glob('**/*.360')):
                size = mp4_path.stat().st_size
                if size > max_size:
                    max_size = size
                    max_path = mp4_path
            
            # Catch the extension before we rename it and lose the .360 name!
            if max_path.suffix.lower() == '.360' or '360' in max_path.name.lower():
                is_360_mapping = True
                
            shutil.move(max_path, mapping_vid_path)
            print(f"raw_videos/mapping.mp4 don't exist! Renaming largest file {max_path.name}.")
        else:
            # If mapping.mp4 was already created in a previous run, safely assume it needs splitting for this rig
            is_360_mapping = True
        
        # create gripper calibration video if don't exist
        gripper_cal_dir = input_dir.joinpath('gripper_calibration')
        if not gripper_cal_dir.is_dir():
            gripper_cal_dir.mkdir()
            print("raw_videos/gripper_calibration don't exist! Creating one with the first video of each camera serial.")
            
            serial_start_dict = dict()
            serial_path_dict = dict()
            with ExifToolHelper() as et:
                for mp4_path in list(input_dir.glob('**/*.MP4')) + list(input_dir.glob('**/*.mp4')) + list(input_dir.glob('**/*.360')):
                    if mp4_path.name.startswith('map'):
                        continue
                    
                    start_date = mp4_get_start_datetime(str(mp4_path))
                    meta = list(et.get_metadata(str(mp4_path)))[0]
                    cam_serial = meta['QuickTime:CameraSerialNumber']
                    
                    if cam_serial in serial_start_dict:
                        if start_date < serial_start_dict[cam_serial]:
                            serial_start_dict[cam_serial] = start_date
                            serial_path_dict[cam_serial] = mp4_path
                    else:
                        serial_start_dict[cam_serial] = start_date
                        serial_path_dict[cam_serial] = mp4_path
            
            for serial, path in serial_path_dict.items():
                print(f"Selected {path.name} for camera serial {serial}")
                out_path = gripper_cal_dir.joinpath(path.name)
                shutil.move(path, out_path)

        # look for mp4 video in all subdirectories in input_dir
        input_mp4_paths = list(input_dir.glob('**/*.MP4')) + list(input_dir.glob('**/*.mp4')) + list(input_dir.glob('**/*.360'))
        print(f'Found {len(input_mp4_paths)} MP4 videos')

        with ExifToolHelper() as et:
            for mp4_path in input_mp4_paths:
                if mp4_path.is_symlink():
                    print(f"Skipping {mp4_path.name}, already moved.")
                    continue

                start_date = mp4_get_start_datetime(str(mp4_path))
                meta = list(et.get_metadata(str(mp4_path)))[0]
                cam_serial = meta['QuickTime:CameraSerialNumber']
                out_dname = 'demo_' + cam_serial + '_' + start_date.strftime(r"%Y.%m.%d_%H.%M.%S.%f")

                # special folders
                if mp4_path.name.startswith('mapping'):
                    out_dname = "mapping"
                elif mp4_path.name.startswith('gripper_cal') or mp4_path.parent.name.startswith('gripper_cal'):
                    out_dname = "gripper_calibration_" + cam_serial + '_' + start_date.strftime(r"%Y.%m.%d_%H.%M.%S.%f")
                
                # create directory
                this_out_dir = output_dir.joinpath(out_dname)
                this_out_dir.mkdir(parents=True, exist_ok=True)
                
                # move videos
                vfname = 'raw_video.mp4'
                out_video_path = this_out_dir.joinpath(vfname)
                shutil.move(mp4_path, out_video_path)
                
                # --- NEW DUAL-LENS BRANCHING LOGIC ---
                # If this is the SLAM mapping video AND it was flagged as a 360 source
                if out_dname == "mapping" and is_360_mapping:
                    print("Running 360 preprocessing split on mapping video...")
                    # Pass the newly moved raw_video.mp4 file into the splitter
                    split_360_video(out_video_path, this_out_dir)

                # create symlink back from original location
                # relative_to's walk_up argument is not avaliable until python 3.12
                dots = os.path.join(*['..'] * len(mp4_path.parent.relative_to(session).parts))
                rel_path = str(out_video_path.relative_to(session))
                symlink_path = os.path.join(dots, rel_path)
                mp4_path.symlink_to(symlink_path)

# %%
if __name__ == '__main__':
    if len(sys.argv) == 1:
        main.main(['--help'])
    else:
        main()
