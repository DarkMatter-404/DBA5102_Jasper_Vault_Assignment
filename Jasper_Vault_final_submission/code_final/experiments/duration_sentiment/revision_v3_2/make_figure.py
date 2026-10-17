#!/usr/bin/env python3
"""Export a presentation figure from the delivered CSV/JSON results."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',default=str(Path(__file__).resolve().parent/'results'));a=p.parse_args();root=Path(a.results)
    info=json.loads((root/'summary.json').read_text());comp=pd.read_csv(root/'component_comparison.csv');comp=comp[comp.population.eq('matched_absolute_fresh_market')]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,(ax,bx)=plt.subplots(1,2,figsize=(13.5,6.5),gridspec_kw={'width_ratios':[1,1.05]});fig.patch.set_facecolor('#f7f9fc')
    fig.suptitle('Combined PP pricing experiment',x=.06,y=.96,ha='left',fontweight='bold',fontsize=23,color='#14263d')
    fig.text(.06,.89,'Extended news and X sentiment | frozen July-1 model | 4,155 validation orders',fontsize=12,color='#526074')
    labels=['Relative factors','Market inputs available','Quotes with fresh social','Social layer applied']
    vals=[info['relative_factor_rows'],info['full_component_eligible'],info['fresh_social_quotes'],info['social_layer_applied_quotes']]
    ax.barh(labels,vals,color=['#bdcadd','#718aa7','#429aa0','#15616d'],height=.58);ax.invert_yaxis();ax.set_xlim(0,4700)
    for i,v in enumerate(vals):ax.text(v+55,i,f'{v:,}',va='center',fontweight='bold',color='#24354a')
    ax.set_title('Where the framework can operate',loc='left',pad=18,fontweight='bold');ax.set_xlabel('Validation orders');ax.set_axisbelow(True);ax.grid(axis='x',alpha=.15)
    vals=comp.aggregate_quote_change.to_numpy()*100;names=['Duration','Market + news','Add social activity','Combined sentiment']
    bx.barh(names,vals,color=['#bdcadd','#718aa7','#429aa0','#15616d'],height=.58);bx.invert_yaxis();bx.set_xlim(0,.83)
    for i,v in enumerate(vals):bx.text(v+.012,i,f'+{v:.3f}%',va='center',fontweight='bold',color='#24354a')
    bx.set_title('Price changes on 474 matched rows',loc='left',pad=18,fontweight='bold',fontsize=12);bx.set_xlabel('Total quoted-premium change (%)\nversus conditional reference');bx.grid(axis='x',alpha=.15);bx.set_axisbelow(True)
    fig.subplots_adjust(left=.21,right=.97,top=.77,bottom=.28,wspace=.85)
    fig.text(.06,.16,'News: 153 records  |  BTC social: 351 snapshots  |  814 quotes change after extending the collection',fontsize=11,color='#14263d',fontweight='bold')
    fig.text(.06,.095,'Quote changes are not profit gains. Payouts are withheld; the 474 absolute-price comparisons use reconstructed references.\nMissing September–October market data triggers the duration fallback. Seven rows are withheld for timing checks.',fontsize=10,color='#526074',linespacing=1.6)
    fig.savefig(root/'framework_results.png',dpi=170,facecolor=fig.get_facecolor());plt.close(fig)

if __name__=='__main__':main()
