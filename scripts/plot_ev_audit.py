"""Render retrospective calibration and same-sample baseline figures with matplotlib."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audits/2026-10-19-ev'
data = json.loads((OUT / 'model-diagnostics.json').read_text())
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), layout='constrained')
for ax, market in zip(axes, ['points', 'threes']):
    m = data['markets'][market]['variants']['frozen']['supported']
    bins = m['reliability']
    ax.plot([0, 1], [0, 1], '--', color='#81909b', label='Perfect calibration')
    ax.plot([b['meanPrediction'] for b in bins], [b['observed'] for b in bins], 'o-', color='#1765a8', label='Supported historical grid')
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel='Predicted probability', ylabel='Observed frequency', title=f"{market.title()} · {m['appearances']:,} appearances / {m['fixtures']} fixtures")
    ax.grid(alpha=.2)
    ax.text(.04, .93, f"Slope {m['calibrationSlope']:.3f}\nIntercept {m['calibrationIntercept']:.3f}\nWeighted error {m['ece']:.3f}", va='top', transform=ax.transAxes)
axes[1].legend(loc='lower right', fontsize=8)
fig.suptitle('EV v1.1: retrospective probability calibration', fontsize=14)
fig.supxlabel('Feb 16–Apr 12, 2026 · already inspected archive · one total weight per player appearance; alternate lines are dependent', fontsize=9)
fig.savefig(OUT / 'calibration.png', dpi=180)
plt.close(fig)
fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.5), layout='constrained')
for ax, market in zip(axes, ['points', 'threes']):
    variants = data['markets'][market]['variants']
    keys = ['frozen', 'seasonMeanCalibrated', 'recentFormCalibrated']
    vals = [variants[k]['supported']['brier'] for k in keys]
    bars = ax.bar(['EV v1.1', 'Season mean', 'Recent form'], vals, color=['#1765a8', '#7e8e9c', '#9eabb6'])
    ax.set(ylim=(0, .23), ylabel='Brier score (lower is better)', title=market.title())
    ax.bar_label(bars, labels=[f'{v:.5f}' for v in vals], padding=4)
    ax.grid(axis='y', alpha=.2)
fig.suptitle('Same supported observations, frozen calibrated baselines', fontsize=14)
fig.supxlabel('Retrospective diagnostics are not prospective edge or profitability evidence. No historical FanDuel offers were available.', fontsize=9)
fig.savefig(OUT / 'baseline-comparison.png', dpi=180)
plt.close(fig)
print('Wrote calibration.png and baseline-comparison.png')
