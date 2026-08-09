#!/usr/bin/env bash
# SSH tunnel: Mac → AutoDL
# Run on Mac to forward Voice/S2S ports.
# Replace <autodl-host> with actual AutoDL hostname.

ssh \
  -L 7860:127.0.0.1:7860 \
  -L 8765:127.0.0.1:8765 \
  -R 8089:127.0.0.1:18089 \
  <autodl-host>
