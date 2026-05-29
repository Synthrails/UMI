import subprocess
import re
import json
import pathlib

def extract_max2_imu(video_path: pathlib.Path, json_path: pathlib.Path):
    """
    Executes the compiled GoPro gpmfdemo binary using a dynamically calculated 
    relative path, parses its text stream, interpolates high-frequency timestamps, 
    and saves a UMI-compatible imu_data.json file.
    """
    # 1. Dynamically locate the gpmfdemo binary relative to this script's position
    # __file__ is synthrails/slam/universal_manipulation_interface/scripts_slam_pipeline/gpmf_adapter.py
    script_dir = pathlib.Path(__file__).parent.resolve()
    
    # Move up two levels to get to the synthrails/slam/ root
    slam_root = script_dir.parents[1] 
    
    # Build the path down into the compiled parser folder
    gpmf_executable = slam_root.joinpath('gpmf-parser', 'demo', 'gpmfdemo')

    if not gpmf_executable.exists():
        raise FileNotFoundError(
            f"Could not locate gpmfdemo binary at verified relative path: {gpmf_executable}\n"
            "Please ensure gpmf-parser is cloned, compiled via 'make', and placed "
            "side-by-side with the universal_manipulation_interface directory."
        )

    print(f"Executing local C-parser on {video_path.name}...")
    
    # 2. Run gpmfdemo synchronously to extract the full telemetry stream
    result = subprocess.run([str(gpmf_executable), str(video_path), '-a', '-f'], capture_output=True, text=True, errors='replace')
    output = result.stdout

    # Initialize the standardized UMI data dictionary layout expected by ORB-SLAM3
    imu_data = {"accelerometer": [], "gyroscope": []}
    
    # Regular expressions to parse text stream values and summary sampling rates
    accl_pattern = re.compile(r'ACCL\s+([-\d.]+)m/s.,\s+([-\d.]+)m/s.,\s+([-\d.]+)m/s.')
    gyro_pattern = re.compile(r'GYRO\s+([-\d.]+)rad/s,\s+([-\d.]+)rad/s,\s+([-\d.]+)rad/s')
    rate_pattern = re.compile(r'([A-Z]{4}) sampling rate = ([\d.]+)Hz \(time ([\d.]+) to')

    # 3. Parse all text stream rows extracted by the binary
    raw_accl = accl_pattern.findall(output)
    raw_gyro = gyro_pattern.findall(output)

    # 4. Extract timing metadata block from the bottom summary table
    rates = {match[1]: {'hz': float(match[2]), 'start': float(match[3])} for match in rate_pattern.finditer(output)}

    # 5. Process Accelerometer (Interpolate timestamps mathematically for each sample)
    if 'ACCL' in rates and raw_accl:
        start_time = rates['ACCL']['start']
        time_step = 1.0 / rates['ACCL']['hz']
        for i, (x, y, z) in enumerate(raw_accl):
            timestamp = start_time + (i * time_step)
            imu_data["accelerometer"].append([timestamp, float(x), float(y), float(z)])

    # 6. Process Gyroscope (Interpolate timestamps mathematically for each sample)
    if 'GYRO' in rates and raw_gyro:
        start_time = rates['GYRO']['start']
        time_step = 1.0 / rates['GYRO']['hz']
        for i, (x, y, z) in enumerate(raw_gyro):
            timestamp = start_time + (i * time_step)
            imu_data["gyroscope"].append([timestamp, float(x), float(y), float(z)])

    # 7. Output the standardized structure back to your session folder
    with open(json_path, 'w') as f:
        json.dump(imu_data, f)
    