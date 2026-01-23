import Pyro5.api
import numpy as np
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "DTMicroscope")))

from DTMicroscope.base.dummy_mic import DummyMicroscope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockServer")

def serialize(array):
    array_list = array.tolist()
    dtype = str(array.dtype)
    return array_list, array.shape, dtype

@Pyro5.api.expose
class TEMServer(object):
    def __init__(self):
        self.microscope = DummyMicroscope()
        self.detectors = {
            'wobbler_camera': {'size': 512, 'exposure': 0.1},
            'ceta_camera': {'size': 512, 'exposure': 0.1}
        }
        self.magnification = 1000.0
        self.stage_position = [0.0, 0.0, 0.0, 0.0, 0.0]

    def get_instrument_status(self, parameters=None):
        logger.info(f"get_instrument_status params={parameters}")
        return {
            'vacuum': 'Ready',
            'column_valve': 'Open',
            'beam_current': 1.0e-9,
            'source': self.microscope.name
        }

    def get_stage(self):
        logger.info("get_stage")
        return self.stage_position

    def set_stage(self, stage_positions, relative=True):
        logger.info(f"set_stage pos={stage_positions} rel={relative}")
        mapping = {'x':0, 'y':1, 'z':2, 'a':3, 'b':4}
        for k, v in stage_positions.items():
            if k in mapping:
                idx = mapping[k]
                if relative:
                    self.stage_position[idx] += v
                else:
                    self.stage_position[idx] = v
        return 1

    def acquire_image(self, device_name, **args):
        logger.info(f"acquire_image device={device_name} args={args}")
        size = 512
        if device_name in self.detectors:
            size_param = self.detectors[device_name].get('size', 512)
            size = (size_param, size_param)
        
        arr = self.microscope.get_overview_image(size=size)
        arr = arr.astype(np.uint16)
        
        return serialize(arr)
        
    def set_microscope_status(self, parameter=None, value=None):
        logger.info(f"set_microscope_status {parameter}={value}")
        if parameter == 'magnification':
            self.magnification = float(value)
        return 1

    def get_detectors(self):
        return list(self.detectors.keys())

    def close(self):
        logger.info("Closing server")
        return 1

def main(host="127.0.0.1", port=9093):
    print(f"Mock Pyro5 Server (DTMicroscope) running on {host}:{port}", flush=True)
    daemon = Pyro5.api.Daemon(host=host, port=port)
    uri = daemon.register(TEMServer, objectId="tem.server")
    print("Server ready. URI:", uri, flush=True)
    daemon.requestLoop()

if __name__ == "__main__":
    port = 9093
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    main(port=port)
