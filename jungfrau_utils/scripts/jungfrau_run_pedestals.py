from datetime import datetime
from time import sleep
import argparse
import os, sys
import subprocess

from detector_integration_api import DetectorIntegrationClient


def reset_bits(client):
    sleep(0.1)
    client.set_detector_value("clearbit", "0x5d 0")
    sleep(0.1)
    client.set_detector_value("clearbit", "0x5d 12")
    sleep(0.1)
    client.set_detector_value("clearbit", "0x5d 13")
    sleep(0.1)


def run(api_address, filename, directory, uid, period, exptime, numberFrames, trigger, analyze, number_bad_modules, instrument=""):
    if api_address == "":
        print("[ERROR] Please specify an API address, like http://sf-daq-alvra:10000 (Alvra) or http://sf-daq-bernina:10000 (Bernina)")
        return
    if uid == 0:
        print("[ERROR] Please specify the user id (the pgroup)")
        return
    if directory == "":
        print("[ERROR] Please specify an output directory")
        return

    client = DetectorIntegrationClient(api_address)

    #client.get_status() empty at this moment

    try:
        writer_config = {"output_file": directory + "/" + filename,
                         "user_id": uid,
                         "n_frames": numberFrames,
                         "general/user": str(uid),
                         "general/process": __name__,
                         "general/created": str(datetime.now()),
                         "general/instrument": instrument
                         }

        if trigger == 0:
            detector_config = {"period": period,
                               "exptime": exptime,
                               "frames": numberFrames,
                               'cycles': 1,
                               "dr": 16}
        else:
            detector_config = {"period": period,
                               "exptime": exptime,
                               "frames": 1, 'cycles': numberFrames,
                               "timing": "trigger",
                               "dr": 16
                               }

        backend_config = {"n_frames": numberFrames,
                          "bit_depth": 16
                          }

        bsread_config = {'output_file': '/dev/null',
                         'user_id': uid,
                         "general/user": str(uid),
                         "general/process": __name__,
                         "general/created": str(datetime.now()),
                         "general/instrument": instrument
                         }

        client.reset()

        configuration = {"writer": writer_config, "backend": backend_config,
                         "detector": detector_config, "bsread": bsread_config}

        client.set_config(configuration)
        print(client.get_config())

        if trigger == 1:
            print("\nPedestal run use external trigger. To have enough statistics --period should be set to right value. Currently %d Hz\n" % int(1/period))

        sleepTime = numberFrames * period / 7

        print("Resetting gain bits on Jungfrau")
        reset_bits(client)

        client.set_detector_value("setbit", "0x5d 0")
        sleep(1) # for the moment there is a delay to make sure detector is in the highG0 mode
        print("Taking data at HG0")
        client.start()

        sleep(sleepTime * 3)

        client.set_detector_value("clearbit", "0x5d 0")
        print("Taking data at G0")
        sleep(sleepTime * 2)

        client.set_detector_value("setbit", "0x5d 12")
        print("Taking data at G1")
        sleep(sleepTime)

        client.set_detector_value("setbit", "0x5d 13")
        print("Taking data at G2")
        sleep(sleepTime)

        print("Waiting for acquisition to finish.")
        try:
            client.wait_for_status(["IntegrationStatus.FINISHED"], polling_interval=0.1)
        except IntegrationStatus.ERROR:
            print("Got IntegrationStatus ERROR")
            print(client.get_status_details())

        print("Reseting acquisition status.")
        client.reset()

        reset_bits(client)

        if analyze:
            print("Running pedestal analysis. It will take some time, you can run in parallel using old pedestal files")
        else:
            print("Will not produce pedestal result files, do manually (it will be faster) using computing nodes:")

        client_status = client.get_status_details()
        enabled_detectors = list(client_status['details'].keys())
        if 'bsread' in enabled_detectors:
            enabled_detectors.remove('bsread')
        print("Following detectors are enabled %s, will run over them" % enabled_detectors)

        for detector in enabled_detectors:
            print("jungfrau_create_pedestals --filename %s --directory %s --verbosity 4" % (writer_config["output_file"] + "." + detector + ".h5", os.path.join(directory.replace("raw", "res"), "")) )
            if analyze:
                try:
                    subprocess.call(["jungfrau_create_pedestals", "--filename", writer_config["output_file"] + "." + detector + ".h5", "--directory",
                                     os.path.join(directory.replace("raw", "res"), ""), "--verbosity", "4"]) 
                except:
                    print("Pedestal analysis failed for detector %s. Do manually." % detector)
                

        print("Done.")

    except KeyboardInterrupt:

        print("CTRL-C caught, stopping and resetting.")

        try:
            client.stop()
            client.reset()
            reset_bits(client)
        except:
            raise Exception("Cannot stop the integration. Check status details or reset services.")

    print("Pedestal run data saved in %s" % writer_config["output_file"])

    return configuration


def main():
    date_string = datetime.now().strftime("%Y%m%d_%H%M")

    parser = argparse.ArgumentParser(description="Create a pedestal file for Jungrau")
    parser.add_argument("--api", default="")
    parser.add_argument("--filename", default="pedestal_%s" % date_string, help="Output file name")
    parser.add_argument("--directory", default="", help="Output directory")
    parser.add_argument("--uid", default=0, help="User ID which needs to own the file", type=int)
    parser.add_argument("--pgroup", default="", help="Same as --uid, but specifying the pgroup instead", type=str)
    parser.add_argument("--period", default=0.01, help="Period (default is 100Hz - 0.01)", type=float)
    parser.add_argument("--exptime", default=0.000010, help="Integration time (default 0.000010 - 10us)", type=float)
    parser.add_argument("--frames", default=4000, help="Number of total frames to be acquired (default 4000)", type=int)
    parser.add_argument("--trigger", default=1, help="run with the trigger, PERIOD will be ignored in this case(default - 1(yes))", type=int)
    parser.add_argument("--analyze", default=False, help="Run the pedestal analysis (default False)", action="store_true")
    parser.add_argument("--number_bad_modules",
                        default=0, help="Number of bad modules in the detector. Makes sense only together with --analyse (default 0)",
                        action="store", type=int)
    parser.add_argument("--instrument", default="", type=str, help="Instrument (either Alvra or Bernina, used only for metadata)", action="store")
    args = parser.parse_args()

    uid = args.uid
    if args.pgroup != "":
        # pgroup is always in the form pXXXXX
        if args.pgroup[0] != "p":
            print("[ERROR] Pgroup must be in the form pXXXXX, e.g. p12345")
            sys.exit(-1)
        uid = int(args.pgroup[1:])

    cfg = run(args.api, args.filename, args.directory, uid, args.period, args.exptime, args.frames, args.trigger, args.analyze, args.number_bad_modules, args.instrument)


if __name__ == "__main__":
    main()
