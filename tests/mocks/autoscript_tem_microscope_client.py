class TemMicroscopeClient:
    def connect(self, host, port):
        print(f"Mockly connected to {host}:{port}")
    
    @property
    def vacuum(self):
        class Vacuum:
            state = "Ready"
            class ColumnValves:
                state = "Open"
                def open(self): pass
                def close(self): pass
            column_valves = ColumnValves()
        return Vacuum()

    @property
    def specimen(self):
        class Specimen:
            class Stage:
                position = [0.0, 0.0, 0.0, 0.0, 0.0]
                def get_holder_type(self): return "SingleTilt"
            stage = Stage()
        return Specimen()

    @property
    def detectors(self):
        class Detectors:
            def get_camera_detector(self, camera_type):
                return "MockDetector"
            class Screen:
                def measure_current(self): return 1e-9
            screen = Screen()
        return Detectors()

    @property
    def acquisition(self):
        class Acquisition:
            def acquire_camera_image(self, camera, size, exposure):
                import numpy as np
                class MockImage:
                    data = np.random.randint(0, 255, (size, size), dtype=np.uint16)
                return MockImage()
        return Acquisition()

class enumerations:
    class CameraType:
        FLUCAM = 1
        BM_CETA = 2

class structures:
    class StagePosition:
        pass
