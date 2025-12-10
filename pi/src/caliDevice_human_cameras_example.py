import camera

def get_human_readable_cameras():
    devices = camera.list_video_devices()
    available = [f"Camera {i} (/dev/video{i})" for i in devices]
    if not available:
        available.append("No cameras detected")
    return available
