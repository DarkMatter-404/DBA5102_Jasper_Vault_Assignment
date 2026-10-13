#!/usr/bin/env python3
"""Rebuild presentation figures for the verified original EN experiment."""
from pathlib import Path
import argparse
import json
import math
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data-dir',type=Path,default=ROOT/'output/data')
parser.add_argument('--output-dir',type=Path,default=ROOT/'output/figures')
args=parser.parse_args()
DATA=args.data_dir
OUT=args.output_dir
FIG=OUT
FIG.mkdir(parents=True,exist_ok=True)
audit=json.loads((DATA/'data_audit.json').read_text())
summary=json.loads((DATA/'analysis_summary.json').read_text())
frozen=json.loads((DATA/'frozen_july_model.json').read_text())
metrics=pd.read_csv(DATA/'july_holdout_metrics.csv').set_index('model')
scenarios=pd.read_csv(DATA/'july_assumed_retention_scenarios.csv')
monthly=pd.read_csv(DATA/'monthly_summary.csv')
stress=pd.read_csv(DATA/'payout_stress.csv')
if audit['valid_analysis_rows'] != 7603 or not math.isclose(metrics.loc['anchor_bps_state_ridge0.1','RMSE_USDC'],144.82358907928326,rel_tol=1e-6):
    raise ValueError('These figures describe the original EN study. Reproduce and verify that study before building figures.')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
TEAL='#087E8B'; GRAY='#788796'; RED='#B84242'; NAVY='#19354A'

def chart_out(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=210,bbox_inches='tight',facecolor='white')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight',facecolor='white')
    plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(11,3.4))
ids=['recorded_bps_scalar_ridge0','anchor_bps_scalar_ridge0','anchor_bps_state_ridge0.1']
labels=['Calibrated\nrecorded premium','Calibrated\nvolatility anchor','Selected\nchallenger']
for ax,metric,ylabel in [(axs[0],'RMSE_USDC','Payout RMSE per order (USDC)'),(axs[1],'calibration_ratio_predicted_to_actual','Predicted payouts / actual payouts')]:
    vals=[metrics.loc[i,metric] for i in ids]
    bars=ax.bar(labels,vals,color=[TEAL,GRAY,RED],width=.65)
    for b,v in zip(bars,vals):
        ax.text(b.get_x()+b.get_width()/2,v+(2 if metric=='RMSE_USDC' else .015),f'{v:.2f}' if metric=='RMSE_USDC' else f'{v:.1%}',ha='center',fontsize=10)
    ax.set_ylabel(ylabel);ax.tick_params(axis='x',labelsize=9)
    ax.set_ylim(0,165 if metric=='RMSE_USDC' else 1.13)
    if metric!='RMSE_USDC':ax.axhline(1,ls='--',color=GRAY,linewidth=1)
fig.tight_layout(w_pad=3);chart_out(fig,'holdout_comparison')

fig,ax=plt.subplots(figsize=(10,3.2))
x=range(len(monthly))
ax.plot(list(x),monthly.claims_to_premium,marker='o',linewidth=2.5,color=TEAL)
ax.axhline(1,ls='--',color=RED,lw=1)
for i,v in enumerate(monthly.claims_to_premium):ax.text(i,v+.035,f'{v:.1%}',ha='center',fontsize=10)
ax.set_xticks(list(x));ax.set_xticklabels(['Feb','Mar','Apr','May','Jun','Jul'])
ax.set_ylabel('Payouts / recorded premiums');ax.set_ylim(.60,1.66)
ax.set_xlabel('2026 order creation month   |   Audited sample, gross of all other costs')
fig.tight_layout();chart_out(fig,'monthly_loss_ratio')

fig,ax=plt.subplots(figsize=(10,3.4))
v=[summary['July_premium_USDC']-summary['July_payout_USDC']]+scenarios.scenario_gross_margin_USDC.tolist()
lab=['Recorded\nprices','Overlay\nno attrition','Overlay\nelasticity 1','Overlay\nelasticity 2','Overlay\nelasticity 4']
bars=ax.bar(lab,v,color=[TEAL,GRAY,RED,RED,RED],width=.65)
for b,y in zip(bars,v):ax.text(b.get_x()+b.get_width()/2,y+(160 if y>=0 else -180),f'{y:,.0f}',ha='center',va='bottom' if y>=0 else 'top',fontsize=10)
ax.axhline(0,color=GRAY,lw=.8);ax.set_ylim(-7300,5500);ax.set_ylabel('July gross margin (USDC)')
ax.tick_params(axis='x',labelsize=10);fig.tight_layout();chart_out(fig,'commercial_scenarios')

def eq(name,latex,width=10,height=.65):
    fig=plt.figure(figsize=(width,height));fig.text(.5,.5,'$'+latex+'$',ha='center',va='center',fontsize=17)
    fig.savefig(FIG/(name+'.png'),dpi=260,bbox_inches='tight',pad_inches=.08,facecolor='white');plt.close(fig)

eq('anchor',r'A_i=N_i\left[2\Phi\left(\frac{\sqrt{v_t H_i}}{2}\right)-1\right]')
eq('cost',r'\widehat{\mu}_i=A_i\exp\left(\beta_0+\sum_{j=1}^{4}\beta_j z_{ij}\right)')
eq('multiplier',r'M_i=\mathrm{clip}\left(c\sqrt{\frac{\widehat{\mu}_i}{\mathrm{LR}_{\mathrm{train}} B_i}},\ 0.85,\ 1.15\right)')
eq('gate',r'P_i=B_i\left[1+w(M_i-1)\right],\qquad 0\leq w\leq 1')
eq('retention',r'a_i(e)=\min\{1,M_i^{-e}\},\qquad G(e)=\sum_i a_i(e)(B_i M_i-Y_i)')

fig,ax=plt.subplots(figsize=(10,3.8));ax.set_xlim(0,10);ax.set_ylim(0,4);ax.axis('off')
boxes=[(0.2,2.3,2.0,.95,'Completed market data\nand order inputs'),(2.8,2.3,2.0,.95,'Off-chain model\nand signed quote'),(5.4,2.3,2.0,.95,'Contract checks\nexpiry nonce limits'),(8.0,2.3,1.8,.95,'Accept premium\nand record PP'),(5.4,.35,2.0,.95,'Reject or requote'),(8.0,.35,1.8,.95,'Verified settlement\nand payout')]
for x,y,w,h,t in boxes:
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.03',edgecolor='#BCCAD3',facecolor='#F3F7F9'))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=10,color=NAVY)
for a,b in [((2.2,2.78),(2.8,2.78)),((4.8,2.78),(5.4,2.78)),((7.4,2.78),(8,2.78)),((6.4,2.3),(6.4,1.30)),((8.9,2.3),(8.9,1.30))]:
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color=GRAY,lw=1.4))
ax.text(7.7,3.05,'pass',ha='center',fontsize=9);ax.text(6.56,1.79,'fail',fontsize=9)
fig.tight_layout();chart_out(fig,'deployment_architecture')


print(f'Saved PNG and SVG figures to {FIG}')
