# Capture Guide

Video capture quality directly affects COLMAP and 2DGS success. Use this guide when recording a foot and checkerboard scene for the AMADEUS pipeline.

## Required Objects

- User's foot
- A4 checkerboard or another checkerboard with known physical dimensions
- Smartphone RGB camera

## Recommended Capture Orbit

Move the camera slowly around the foot while keeping both the foot and checkerboard visible. Adjacent frames should overlap enough for COLMAP to match visual features.

![Recommended camera orbit around the foot](assets/capture-orbit-guide.png)

## Recommended Scene

- Use bright and even lighting.
- Avoid strong reflections on the floor.
- Keep the foot and checkerboard inside the frame.
- Avoid moving background objects.
- Keep the checkerboard fixed during the entire capture.

## Foot Position

- The full foot should remain visible throughout the video.
- Toes, instep, heel, and the bottom reference plane should not be heavily occluded.
- Place the checkerboard next to or under the foot so it belongs to the same reconstructed scene.

## Camera Motion

Recommended:

- Move slowly around the foot in a smooth orbit.
- Keep enough overlap between consecutive frames.
- Maintain focus and stable exposure.
- Capture the foot from multiple side and top-side angles.

Avoid:

- Fast rotation
- Sudden camera shakes
- Frames where the foot or checkerboard leaves the image
- Strong shadows covering the foot
- Long stretches of blurry frames

## Checkerboard

The checkerboard is the scale reference.

Recommended:

- Use a printed A4 checkerboard.
- Record the real physical dimensions.
- Keep it flat and fixed.
- Make sure its corners and grid lines are visible across many frames.

## Failure Reduction Checklist

After recording, check the following:

- Are there enough frames where the foot and checkerboard are visible together?
- Are most frames sharp and well exposed?
- Is motion blur limited?
- Are there enough trackable visual features for COLMAP?
- Are the checkerboard corners/grid lines clear?
- Is the camera orbit slow enough for adjacent-frame overlap?

## Privacy

Foot videos should be treated as private biometric-like data.

- Do not commit raw videos to a public repository.
- Use consented demo data or synthetic/sample data for public demos.
- Keep training datasets under a separate access and release policy.
