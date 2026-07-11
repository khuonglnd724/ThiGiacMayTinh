from backend.main import build_simulated_conveyor_frames, is_defect_frame


def test_build_simulated_conveyor_frames():
    frames = build_simulated_conveyor_frames(frames=4, interval_ms=500, confidence=0.25)

    assert len(frames) == 4
    assert frames[0]["verdict"] == "PASS"
    assert frames[2]["defect_count"] >= 1
    assert all("image_url" in frame for frame in frames)
    assert all(frame["frame_index"] == index + 1 for index, frame in enumerate(frames))


def test_is_defect_frame_uses_predictions_as_signal():
    assert is_defect_frame([
        {"class_name": "scratch", "confidence": 0.92}
    ]) is True
    assert is_defect_frame([]) is False
    assert is_defect_frame([
        {"class_name": "product", "confidence": 0.8}
    ]) is True
