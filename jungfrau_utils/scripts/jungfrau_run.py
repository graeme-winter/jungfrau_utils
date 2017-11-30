from datetime import datetime
from time import sleep
import argparse
import os
import subprocess

from detector_integration_api import DetectorIntegrationClient


def reset_bits(client):
    sleep(1)
    print(client.set_detector_value("clearbit", "0x5d 0"))
    sleep(1)
    print(client.set_detector_value("clearbit", "0x5d 12"))
    sleep(1)
    print(client.set_detector_value("clearbit", "0x5d 13"))
    sleep(1)


def run_jungfrau(n_frames, save=True, exptime=0.000010, outfile="", outdir="", uid=16852, api_address="http://sf-daq-1:10001", gain_filename="", pede_filename=""):
    client = DetectorIntegrationClient(api_address)

    client.get_status()

    #print("Resetting gain bits on Jungfrau")
    #reset_bits(client)

    writer_config = {"output_file": outdir + "/" + outfile, "process_uid": uid, "process_gid": uid, "dataset_name": "jungfrau/data", "disable_processing": False, "n_messages": n_frames}
    if not save:
        writer_config["disable_processing"] = True

    print(writer_config)
    detector_config = {"exptime": exptime, "frames": 1, 'cycles': n_frames, "timing": "trigger"}
    backend_config = {"n_frames": n_frames}
    bsread_config = {'output_file': "/dev/null", 'process_uid': args.uid, 'process_gid': args.uid, 'channels': []}

    if gain_filename != "" or pede_filename != "":
        backend_config["gain_corrections_filename"] = gain_filename
        backend_config["gain_corrections_dataset"] = "gains"
        backend_config["pede_corrections_filename"] = pede_filename
        backend_config["pede_corrections_dataset"] = "gains"
        backend_config["activate_corrections_preview"] = True
        print("Corrections in online viewer activated")

    client.reset()
    client.set_config(writer_config=writer_config, backend_config=backend_config, detector_config=detector_config, bsread_config=bsread_config)
    print(client.get_config())

    print("Starting acquisition")
    client.start()

    status = client.get_status()
    while status != "AAAAAAAAAAAAAAAA0":
        sleep(1)
        status = client.get_status()

    print("Stopping acquisition")
    client.reset()
    print("Done")


def main():
    
    date_string = datetime.now().strftime("%Y%m%d_%H%M")

    parser = argparse.ArgumentParser(description="Create a pedestal file for Jungrau")
    parser.add_argument("--api", default="http://sf-daq-1:10000")
    parser.add_argument("--filename", default="run_%s.h5" % date_string, help="Output file name")
    parser.add_argument("--pede", default="", help="File containing pedestal corrections")
    parser.add_argument("--gain", default="", help="File containing gain corrections")
    parser.add_argument("--directory", default="/sf/bernina/data/raw/p16582", help="Output directory")
    parser.add_argument("--uid", default=16582, help="User ID which needs to own the file", type=int)
    parser.add_argument("--period", default=0.01, help="Period (default is 10Hz - 0.01)", type=float)
    parser.add_argument("--exptime", default=0.000010, help="Integration time (default 0.000010 - 10us)", type=float)
    parser.add_argument("--frames", default=10000, help="Integration time (default 10000)", type=int)
    parser.add_argument("--save", default=False, help="Save data file", action="store_true")
    args = parser.parse_args()

    run_jungfrau(args.frames, save=args.save, args.exptime, outfile=args.filename, outdir=args.directory, uid=args.uid, api_address=args.api, gain_filename=args.gain, pede_filename=args.pede)

    
if __name__ == "__main__":
    main()
