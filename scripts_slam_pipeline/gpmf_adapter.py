import subprocess
import re
import pathlib
import csv
import numpy as np

def extract_max2_imu(video_path: pathlib.Path, csv_path: pathlib.Path):
    """
    Executes the compiled GoPro gpmfdemo binary, parses its text stream, 
    interpolates the slower Accelerometer data to match the faster Gyroscope 
    clock, and saves a RealSense-compatible imu_data.csv file.
    """
    script_dir = pathlib.Path(__file__).parent.resolve()
    slam_root = script_dir.parents[1] 
    
    gpmf_executable = slam_root.joinpath('gpmf-parser', 'demo', 'gpmfdemo')

    if not gpmf_executable.exists():
        raise FileNotFoundError(
            f"Could not locate gpmfdemo binary at verified relative path: {gpmf_executable}\n"
            "Please ensure gpmf-parser is compiled."
        )

    print(f"Executing local C-parser on {video_path.name}...")
    
    # Run gpmfdemo synchronously
    result = subprocess.run([str(gpmf_executable), str(video_path), '-a', '-f'], capture_output=True, text=True, errors='replace')
    output = result.stdout
    
    accl_pattern = re.compile(r'ACCL\s+([-\d.]+)m/s.,\s+([-\d.]+)m/s.,\s+([-\d.]+)m/s.')
    gyro_pattern = re.compile(r'GYRO\s+([-\d.]+)rad/s,\s+([-\d.]+)rad/s,\s+([-\d.]+)rad/s')
    rate_pattern = re.compile(r'([A-Z]{4}) sampling rate = ([\d.]+)Hz \(time ([\d.]+) to')

    raw_accl = accl_pattern.findall(output)
    raw_gyro = gyro_pattern.findall(output)
    rates = {match[1]: {'hz': float(match[2]), 'start': float(match[3])} for match in rate_pattern.finditer(output)}

    # Process Accelerometer Arrays
    accel_times = []
    accel_vals = []
    if 'ACCL' in rates and raw_accl:
        start_time = rates['ACCL']['start']
        time_step = 1.0 / rates['ACCL']['hz']
        for i, (x, y, z) in enumerate(raw_accl):
            accel_times.append(start_time + (i * time_step))
            accel_vals.append([float(x), float(y), float(z)])

    # Process Gyroscope Arrays
    gyro_times = []
    gyro_vals = []
    if 'GYRO' in rates and raw_gyro:
        start_time = rates['GYRO']['start']
        time_step = 1.0 / rates['GYRO']['hz']
        for i, (x, y, z) in enumerate(raw_gyro):
            gyro_times.append(start_time + (i * time_step))
            gyro_vals.append([float(x), float(y), float(z)])

    if not accel_times or not gyro_times:
        print("Warning: Missing IMU data in this video track!")
        return

    # Convert to Numpy Arrays for fast math
    accel_times = np.array(accel_times)
    accel_vals = np.array(accel_vals)
    gyro_times = np.array(gyro_times)
    gyro_vals = np.array(gyro_vals)

    # The Math: Interpolate Accel X, Y, Z to perfectly align with Gyro timestamps
    interp_accel_x = np.interp(gyro_times, accel_times, accel_vals[:, 0])
    interp_accel_y = np.interp(gyro_times, accel_times, accel_vals[:, 1])
    interp_accel_z = np.interp(gyro_times, accel_times, accel_vals[:, 2])

    # Output the CSV matching RealSense formatting requirements
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write the header (The C++ binary explicitly skips line 1, so we must provide it)
        writer.writerow(['timestamp', 'ax', 'ay', 'az', 'gx', 'gy', 'gz'])
        
        for i in range(len(gyro_times)):
            writer.writerow([
                f"{gyro_times[i]:.6f}",
                f"{interp_accel_x[i]:.6f}",
                f"{interp_accel_y[i]:.6f}",
                f"{interp_accel_z[i]:.6f}",
                f"{gyro_vals[i, 0]:.6f}",
                f"{gyro_vals[i, 1]:.6f}",
                f"{gyro_vals[i, 2]:.6f}"
            ])
            
    print("Telemetry interpolation and CSV export complete.")