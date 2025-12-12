
class SetActiveCameraRequest(BaseModel):
    camera_path: Optional[str] = None

@app.post("/api/set_active_camera")
async def set_active_camera(request: SetActiveCameraRequest):
    global active_camera_context
    active_camera_context = request.camera_path
    mode = "Single Camera: " + request.camera_path if request.camera_path else "Multi-Camera (All)"
    print(f"Active camera context updated to: {active_camera_context} ({mode})", file=sys.stderr)
    return JSONResponse({"status": "success", "message": f"Context set to {mode}"})
