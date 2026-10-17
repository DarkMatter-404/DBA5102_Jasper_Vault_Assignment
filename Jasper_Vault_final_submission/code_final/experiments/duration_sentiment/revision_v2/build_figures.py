#!/usr/bin/env python3
"""Presentation figures drawn only from regenerated v2 evidence tables."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'output/v2'
FIG=OUT/'figures'
NAVY='#183344';TEAL='#12877f';ORANGE='#d67730';GREY='#82939e'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.spines.left':False,'axes.labelcolor':NAVY,
                     'text.color':NAVY,'xtick.color':NAVY,'ytick.color':NAVY,
                     'savefig.facecolor':'white'})


def save(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=200,bbox_inches='tight')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)


def main():
    FIG.mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(OUT/'commercial_scenarios.csv')
    month=data[data.elasticity.eq(4)].pivot(index='period',columns='policy',values='gross_margin_USDC')
    delta=month.v2_candidate-month.recorded_reference
    assert np.isclose(delta.loc['2026-07'],500.839755157,atol=.001)
    fig,ax=plt.subplots(figsize=(10,5.8))
    colors=[ORANGE if v<0 else TEAL for v in delta]
    ax.bar(['April','May','June','July*'],delta,color=colors,width=.54)
    ax.axhline(0,color=GREY,lw=.9)
    ax.set_ylabel('Candidate minus recorded gross margin (USDC)')
    ax.set_ylim(-135,625)
    ax.set_title('Margin falls in April–May; rises in June–July',loc='left',fontsize=18,pad=22)
    for i,v in enumerate(delta):ax.text(i,v+(17 if v>=0 else -17),f'{v:+,.2f}',ha='center',va='bottom' if v>=0 else 'top',fontweight='bold')
    fig.text(.125,-.005,'Assumed elasticity 4. Retained buyers keep their observed payouts; all costs excluded.\n*July had already been inspected. These are retrospective scenario results, not actual repricing profits.',fontsize=9,color=GREY)
    save(fig,'monthly_margin_change')
    boot=pd.DataFrame(json.loads((OUT/'conditional_bootstrap.json').read_text()))
    boot=boot[boot.elasticity.eq(4)].set_index('comparator').loc[['recorded_reference','uniform_equal_quoted_premium','uniform_equal_order_retention']]
    labels=['Recorded premium','Uniform: same total quote premium','Uniform: same assumed retention']
    means=boot.gross_margin_difference_USDC.to_numpy()
    lower=boot.conditional_95pct_low.to_numpy();upper=boot.conditional_95pct_high.to_numpy()
    fig,ax=plt.subplots(figsize=(10,5.5))
    y=np.arange(3)
    ax.errorbar(means,y,xerr=[means-lower,upper-means],fmt='o',color=TEAL,ecolor=TEAL,markersize=8,capsize=5,lw=2)
    ax.axvline(0,color=GREY,lw=1)
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_ylim(2.5,-.6)
    ax.set_xlim(-220,1150);ax.set_xlabel('Candidate minus comparator scenario gross margin (USDC)')
    ax.set_title('An advantage over uniform pricing is not established',loc='left',fontsize=17,pad=22)
    for j,v in enumerate(means):ax.annotate(f'{v:+,.2f}',(v,j),xytext=(0,-20),textcoords='offset points',ha='center',fontweight='bold')
    fig.text(.125,-.03,'July, assumed elasticity 4; 2,000 paired creation-day resamples. Conditional 95% intervals.\nIntervals exclude demand and model-selection uncertainty. Uniform matches use the evaluation quote mix.',fontsize=9,color=GREY)
    save(fig,'conditional_margin_comparison')
    costs=pd.read_csv(OUT/'cost_metrics.csv').query("period == '2026-07'").set_index('model')
    vals=[costs.loc['calibrated_recorded_reference','RMSE_USDC'],costs.loc['duration_credibility_200','RMSE_USDC']]
    fig,ax=plt.subplots(figsize=(8,4.8))
    ax.barh(['Calibrated reference','Revised duration model'],vals,color=[GREY,TEAL],height=.45)
    ax.invert_yaxis();ax.set_xlim(0,155);ax.set_xlabel('July payout RMSE (USDC); lower is better')
    ax.set_title('Revised payout forecasts remain slightly worse',loc='left',fontsize=17,pad=20)
    for j,v in enumerate(vals):ax.text(v+2,j,f'{v:.2f}',va='center',fontweight='bold')
    fig.text(.125,-.025,'Same 2,625 audited July orders. Pricing gains and payout prediction accuracy are separate claims.',fontsize=9,color=GREY)
    save(fig,'july_cost_accuracy')
    print(f'Three PNG/SVG figures saved to {FIG}')


if __name__=='__main__':main()
