"""
python scripts_slam_pipeline/01_extract_gopro_imu.py data_workspace/cup_in_the_wild/20240105_zhenjia_packard_2nd_conference_room
"""
# %%
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT_DIR)
os.chdir(ROOT_DIR)

# %%
import pathlib
import click
import multiprocessing
from tqdm import tqdm
from scripts_slam_pipeline.gpmf_adapter import extract_max2_imu

# %%
@click.command()
@click.option('-d', '--docker_image', default="chicheng/openicc:latest")
@click.option('-n', '--num_workers', type=int, default=None)
@click.option('-np', '--no_docker_pull', is_flag=True, default=False, help="pull docker image from docker hub")
@click.argument('session_dir', nargs=-1)
def main(docker_image, num_workers, no_docker_pull, session_dir):
    if num_workers is None:
        num_workers = multiprocessing.cpu_count()

    for session in session_dir:
        input_dir = pathlib.Path(os.path.expanduser(session)).joinpath('demos')
        input_video_dirs = [x.parent for x in input_dir.glob('*/raw_video.mp4')]
        print(f'Found {len(input_video_dirs)} video dirs')

        with tqdm(total=len(input_video_dirs)) as pbar:
            for video_dir in tqdm(input_video_dirs):
                video_dir = video_dir.absolute()
                if video_dir.joinpath('imu_data.json').is_file():
                    print(f"imu_data.json already exists, skipping {video_dir.name}")
                    pbar.update(1)
                    continue

                video_path = video_dir.joinpath('raw_video.mp4')
                json_path = video_dir.joinpath('imu_data.json')

                # Run the native GoPro Max 2 telemetry extraction adapter synchronously
                print(f"Extracting telemetry for {video_dir.name}...")
                extract_max2_imu(video_path, json_path)

                if json_path.exists():
                    pbar.update(1)

        print("Done!")

# %%
if __name__ == "__main__":
    main()