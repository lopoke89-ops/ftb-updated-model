"""Independently trace saved points-ladder estimates; never refit model weights."""
import argparse, hashlib, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def mean(rows,key): return sum(r[key] for r in rows)/len(rows)
def clamp(v,a,b): return max(a,min(b,v))
def valid(p):
    return p.get('played') is True and all(isinstance(p.get(k),(int,float)) and p[k]>=0 for k in ['points','fgm','fga','threeMade','threeAttempted','ftm','fta','minutes']) and p['threeMade']<=p['fgm']<=p['fga'] and p['threeMade']<=p['threeAttempted']<=p['fga'] and p['ftm']<=p['fta'] and 2*p['fgm']+p['threeMade']+p['ftm']==p['points']
def cdf(mu,alpha,k):
    if k<0:return 0.
    if not mu:return 1.
    r=1/alpha;q=mu/(r+mu)
    # Independent log-gamma evaluation, not the production mass recurrence.
    return clamp(sum(math.exp(math.lgamma(y+r)-math.lgamma(r)-math.lgamma(y+1)+r*math.log(r/(r+mu))+y*math.log(q)) for y in range(math.floor(k)+1)),0,1)
def calibrated(p,cal):
    if p in (0,1):return p
    z=cal['a']*math.log(p/(1-p))+cal['b'];return 1/(1+math.exp(-clamp(z,-40,40)))
def audit(snapshot,archive,model):
    checks=[];rows=[];contexts={};displayed=set(snapshot.get('displayedSelectionKeys',[]))
    for result in snapshot['results']:
        q=result['quote']
        if q['market']!='points' or q['side']!='at-least':continue
        fixture=next(f for f in snapshot['fixtures'] if f['id']==q['fixtureId'])
        history=[{**p,'date':g['date'],'gameId':g['id']} for g in sorted(archive['games'],key=lambda g:(g['date'],g['id'])) if g['phase']=='regular-season' and g['date']<fixture['date'] for p in g['teams'].get(q['team'],{}).get('players',[]) if str(p['id'])==q['playerId'] and valid(p)]
        recent=history[-20:];n=len(recent);weights=[.94**(n-1-i) for i in range(n)];ws=sum(weights)
        avg=lambda key:sum(w*r[key] for w,r in zip(weights,recent))/ws
        blend=lambda a,b:(a*n+b*5)/(n+5)
        minutes=blend(avg('minutes'),mean(history,'minutes'))
        attempts=lambda key:minutes*blend(avg(key)/max(.1,avg('minutes')),sum(r[key] for r in history)/sum(r['minutes'] for r in history))
        fga,three,fta=[attempts(k) for k in ['fga','threeAttempted','fta']]
        two_m=sum(r['fgm']-r['threeMade'] for r in history);two_a=sum(r['fga']-r['threeAttempted'] for r in history)
        p2=(sum(r['fgm']-r['threeMade'] for r in recent)+(two_m+1)/(two_a+2)*40)/(sum(r['fga']-r['threeAttempted'] for r in recent)+40)
        pct=lambda m,a:(sum(r[m] for r in recent)+(sum(r[m] for r in history)+1)/(sum(r[a] for r in history)+2)*40)/(sum(r[a] for r in recent)+40)
        p3,pft=pct('threeMade','threeAttempted'),pct('ftm','fta');base=2*max(0,fga-three)*p2+3*three*p3+fta*pft
        f=result['features'];config=model['markets']['points'];
        if fixture['date'] not in contexts:
            league={};teams={}
            group=lambda raw:{'PG':'G','SG':'G','SF':'F','PF':'F','G':'G','F':'F','C':'C','GUARD':'G','FORWARD':'F','CENTER':'C'}.get(str(raw).upper())
            for game in archive['games']:
                if game['date']>=fixture['date'] or game['phase']!='regular-season':continue
                for team in [game['home'],game['away']]:
                    own=teams.setdefault(team,{'games':0,'own':{},'allowed':{}});own['games']+=1
                    for side,is_own in [(team,True),(game['away'] if team==game['home'] else game['home'],False)]:
                        for p in game['teams'][side]['players']:
                            role=group(p.get('officialPosition') or p.get('rawPosition'))
                            if not valid(p) or not role:continue
                            b=own['own' if is_own else 'allowed'].setdefault(role,{'points':0,'minutes':0});b['points']+=p['points'];b['minutes']+=p['minutes']
                            if is_own:
                                b=league.setdefault(role,{'points':0,'minutes':0});b['points']+=p['points'];b['minutes']+=p['minutes']
            contexts[fixture['date']]=(league,teams)
        league,teams=contexts[fixture['date']];role=f['role'];opponent=fixture['away'] if q['team']==fixture['home'] else fixture['home'];rate=league[role]['points']/league[role]['minutes']
        def ratio(team,key):
            b=teams[team][key][role];games=teams[team]['games'];return math.exp(clamp(math.log(max(.01,(b['points']/b['minutes'])/rate)),-.7,.7)*games/(games+20))
        offense,defense=ratio(q['team'],'own'),ratio(opponent,'allowed')
        assert abs(offense-f['ratios']['points']['offense'])<1e-10 and abs(defense-f['ratios']['points']['defense'])<1e-10
        season_mean=mean(history,'points');variance=sum((r['points']-season_mean)**2 for r in history)/(len(history)-1);observed_alpha=clamp((variance-season_mean)/(season_mean**2),.01,2)
        mu=(season_mean if config['meanMode']=='season-mean' else base)*defense**config['defensePower']*offense**config['offensePower']
        alpha=clamp(config['alpha']*(1-config.get('dispersionBlend',0))+observed_alpha*config.get('dispersionBlend',0),.01,2)
        raw=1-cdf(mu,alpha,q['line']-1);win=1-calibrated(1-raw,config['calibration']);ev=win*q['decimal']-1
        actual=[minutes,fga,three,fta,base,season_mean,mu,alpha,win,ev];expected=[f['minutes'],f['fga'],f['threePa'],f['fta'],f['base']['points'],f['baseline']['points'],result['rawProjection'],result['dispersion'],result['probabilities']['win'],result['ev']]
        assert all(abs(a-b)<1e-8 for a,b in zip(actual,expected)),(q['player'],actual,expected)
        hits=sum(r['points']>=q['line'] for r in history);recent_hits=sum(r['points']>=q['line'] for r in recent)
        rows.append({'player':q['player'],'playerId':q['playerId'],'team':q['team'],'fixtureId':q['fixtureId'],'line':q['line'],'american':q['american'],'decimal':q['decimal'],'quoteCapturedAt':q['capturedAt'],'displayed':q['key'] in displayed,'historyThrough':history[-1]['date'],'sourceGameIds':[r['gameId'] for r in history],'appearances':len(history),'seasonMean':season_mean,'seasonMinutes':mean(history,'minutes'),'recentWeightedMinutes':avg('minutes'),'blendedHistoricalMinutes':minutes,'recentStarterRate':sum(r['starter'] for r in recent)/n,'projectedFGA':fga,'projected3PA':three,'projectedFTA':fta,'shootingBasedMean':base,'offenseRatio':f['ratios']['points']['offense'],'defenseRatio':f['ratios']['points']['defense'],'rawMean':mu,'calibratedMean':result['projection'],'historicalVariance':variance,'historicalStdDev':math.sqrt(variance),'empiricalDispersion':observed_alpha,'fittedDispersion':alpha,'rawDistributionVariance':mu+alpha*mu*mu,'rawThresholdProbability':raw,'calibratedThresholdProbability':win,'breakEven':1/q['decimal'],'estimatedEV':ev,'historicalHits':hits,'historicalHitRate':hits/len(history),'recentHits':recent_hits,'recentHitRate':recent_hits/n,'sensitivity':[{'historicalExposureScale':scale,'rawMean':mu*scale,'thresholdProbability':1-calibrated(cdf(mu*scale,alpha,q['line']-1),config['calibration'])} for scale in [.5,.75,1,1.25]],'limitations':['Minutes are a weighted historical proxy, not a game-specific playing-time forecast.','Prior-season transfer, lineup changes and injury effects have not been prospectively validated.','The fitted count variance and CDF calibration can enlarge ladder tails.','Observed historical hit rates are descriptive comparisons, not alternative validated forecasts.']})
    rows.sort(key=lambda r:-r['estimatedEV'])
    return {'version':'points-ladder-trace-v1','status':'arithmetic-and-source-trace-passed-no-edge-approval','snapshotId':snapshot['id'],'capturedAt':snapshot['capturedAt'],'sourceEvidenceHash':archive['meta']['evidenceContentHash'],'modelVersion':model['version'],'modelHash':model['modelHash'],'engineHash':model['engineHash'],'auditorHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checks':{'reconstructedLadders':len(rows),'numericComparisons':len(rows)*12,'sameDayAndLaterExcluded':True,'outcomesUsedToFit':False,'weightsChanged':False},'rows':rows,'conclusion':'The large estimates reproduce from historical opportunity, fitted variance/calibration and long offered odds. Correct EV arithmetic does not establish forecast accuracy or profitable edge. Retain frozen weights; audit role/exposure assumptions and collect prospective results.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,default=ROOT/'.pbp/day-review-2026-10-20/latest-snapshot.json');p.add_argument('--output',type=Path,default=ROOT/'audits/2026-10-21-complete-improvements/points-ladder-audit.json');a=p.parse_args()
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    report=audit(read(a.snapshot),read(ROOT/'nba ftb shi/analyst_data.json'),read(ROOT/'nba ftb shi/ev_model.json'));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps({'checks':report['checks'],'keldon20':next(r for r in report['rows'] if r['player']=='Keldon Johnson' and r['line']==20)}))
