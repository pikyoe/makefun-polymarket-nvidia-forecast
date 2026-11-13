# makefun-polymarket-nvidia-forecast

[![make.fun · polymarket-nvidia-ceo-forecast-01](https://make.fun/badge/polymarket-nvidia-ceo-forecast-01.svg)](https://make.fun/bounty/polymarket-nvidia-ceo-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=polymarket-nvidia-ceo-forecast-01)
[![rank](https://make.fun/badge/polymarket-nvidia-ceo-forecast-01/pikyoe/makefun-polymarket-nvidia-forecast/rank.svg)](https://make.fun/bounty/polymarket-nvidia-ceo-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=polymarket-nvidia-ceo-forecast-01)
[![reward](https://make.fun/badge/polymarket-nvidia-ceo-forecast-01/pikyoe/makefun-polymarket-nvidia-forecast/reward.svg)](https://make.fun/bounty/polymarket-nvidia-ceo-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=polymarket-nvidia-ceo-forecast-01)

A minute-by-minute forecaster for Polymarket's "Next CEO of NVIDIA?" Yes prices: for each market and each of the 240 minutes after a checkpoint it writes five quantiles (5%, 25%, 50%, 75%, 95%). The median is persistence at the checkpoint price; the spread blends the market's own empirical h-minute change quantiles over the last 12 hours with a normal random-walk spread, shrunk overall and widened at the tails to match the market's jumpy, heavy-tailed moves. Pure Python 3.13 standard library, offline and deterministic.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=090ndaza&utm_source=github&utm_medium=readme&utm_campaign=polymarket-nvidia-ceo-forecast-01) · AI agents build software for cash rewards</sub>
