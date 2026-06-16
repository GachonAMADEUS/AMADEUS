# AMADEUS runnable pipeline

This directory contains the current runnable AMADEUS pipeline.

## Entry point

```bash
./run_pipeline.sh "input_video.mp4"
./run_pipeline.sh --exhaustive "input_video.mp4"
./run_pipeline.sh --from_step_2 "input_video.mp4"
```

Run commands from this `code/` directory.

## Runtime files not committed

The pipeline expects large or private runtime files to be provided locally:

- `assets/best.pt`
- `assets/sam_vit_h_4b8939.pth`
- `vocab_tree_flickr100K_words32K.bin`
- `tools/orca/...`
- input `.mp4` files

Generated reconstruction and print outputs are intentionally ignored.
