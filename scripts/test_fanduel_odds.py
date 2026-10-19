import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from email.message import Message
from urllib.error import HTTPError
from email.utils import format_datetime
import fanduel_odds as fd

FIXTURE = {'id':'401909088','date':'2026-10-20','home':'DET','away':'BOS','season':'2026-27','phase':'regular-season','scheduledTipoff':'2026-10-20T19:00:00.000Z','status':'pre','names':{'home':['Detroit Pistons'],'away':['Boston Celtics']}}
EVENT = {'eventId':35928218,'eventTypeId':7522,'competitionId':10547864,'name':'Boston Celtics @ Detroit Pistons','openDate':FIXTURE['scheduledTipoff'],'inPlay':False}
ROSTER = [{'id':'1','name':'Player One','team':'BOS'},{'id':'2','name':'Jabari Smith Jr.','team':'DET'}]
STAMP = '2026-10-19T02:00:00+00:00'

def runner(name='Player One Over',side='OVER',line=20.5):
    return {'selectionId':10,'runnerName':name,'result':{'type':side},'handicap':line,'runnerStatus':'ACTIVE','isPlayerSelection':True,
            'winRunnerOdds':{'americanDisplayOdds':{'americanOddsInt':100},'trueOdds':{'decimalOdds':{'decimalOdds':2}}}}

def payload(kind='PLAYER_A_TOTAL_POINTS',name='Player One - Points',runners=None,tab='Player Points'):
    return {'attachments':{'events':{'35928218':copy.deepcopy(EVENT)},'markets':{'m':{'marketId':'747.1','eventId':35928218,'eventTypeId':7522,'inPlay':False,'marketType':kind,'marketName':name,'marketStatus':'OPEN','runners':runners or [runner()]}}},
            'layout':{'tabs':{'1':{'title':tab}},'cards':{'1':{'title':tab,'attachmentsFullyLoaded':True}}}}

class Contracts(unittest.TestCase):
    def parse(self,p,roster=ROSTER,tab='player-points'):
        return fd.parse_markets(p,FIXTURE,EVENT,roster,STAMP,tab)

    def test_exact_full_game_ou_preserves_canonical_ids_target_and_capture(self):
        quotes,issues=self.parse(payload())
        self.assertFalse(issues);q=quotes[0]
        self.assertEqual((q['playerId'],q['fixtureId'],q['line'],q['side']),('1','401909088',20.5,'over'))
        self.assertEqual(q['capturedAt'],STAMP);self.assertEqual(q['decimal'],2);self.assertEqual(q['region'],'TN')
        self.assertIn('boston-celtics-@-detroit-pistons-35928218',q['source'])

    def test_first_team_market_is_own_team_first_score_not_game_first_basket(self):
        r=runner('Player One',line=0);r['result']={}
        p=payload('FIRST_TEAM_BASKET_SCORER','First Team Basket Scorer',[r],'Quick Bets')
        quotes,issues=self.parse(p,tab='quick-bets');self.assertFalse(issues)
        q=quotes[0];self.assertEqual((q['market'],q['period'],q['side'],q['line']),('first-team-basket','team-first-score','yes',None))
        self.assertEqual(q['scoringDefinition'],'first-team-score-including-free-throws');self.assertEqual(q['settlement'],'starter-required')
        for kind in ['FIRST_BASKET_(SAME_GAME_MULTIS)','TEAM_TO_SCORE_FIRST','OVERTIME_FIRST_TEAM_BASKET_SCORER']:
            bad=copy.deepcopy(p);bad['attachments']['markets']['m']['marketType']=kind;self.assertFalse(self.parse(bad,tab='quick-bets')[0])

    def test_first_team_labels_handicap_duplicates_and_incomplete_quick_bets_fail(self):
        r=runner('Player One',line=0);r['result']={}
        p=payload('FIRST_TEAM_BASKET_SCORER','First Team Basket Scorer',[r],'Quick Bets')
        bad=copy.deepcopy(p);bad['attachments']['markets']['m']['marketName']='First Basket';self.assertFalse(self.parse(bad,tab='quick-bets')[0])
        bad=copy.deepcopy(p);bad['attachments']['markets']['m']['runners'][0]['handicap']=1;self.assertFalse(self.parse(bad,tab='quick-bets')[0])
        bad=copy.deepcopy(p);bad['attachments']['markets']['m']['runners'].append({**r,'selectionId':11})
        with self.assertRaises(ValueError):self.parse(bad,tab='quick-bets')
        p['layout']['cards']['1']['attachmentsFullyLoaded']=False
        with self.assertRaises(ValueError):self.parse(p,tab='quick-bets')

    def test_milestones_use_market_target_not_zero_handicap(self):
        q,issues=self.parse(payload('TO_SCORE_25+_POINTS','To Score 25+ Points',[runner('Player One',line=0)]))
        self.assertFalse(issues);self.assertEqual((q[0]['line'],q[0]['side']),(25,'at-least'))
        q,_=self.parse(payload('3+_MADE_THREES','3+ Made Threes',[runner('Player One',line=0)],'Player Threes'),tab='player-threes')
        self.assertEqual((q[0]['line'],q[0]['market']),(3,'threes'))

    def test_milestone_labels_must_agree_with_threshold_and_quarter_lines_are_unsupported(self):
        quotes,issues=self.parse(payload('TO_SCORE_25+_POINTS','To Score 20+ Points',[runner('Player One')]))
        self.assertFalse(quotes);self.assertIn('Milestone target/name mismatch',issues)
        quotes,issues=self.parse(payload(runners=[runner(line=20.25)]))
        self.assertFalse(quotes);self.assertIn('Invalid target',issues)

    def test_quarters_combos_and_unknown_market_types_never_enter_full_game_ev(self):
        for kind in ['PLAYER_A_1ST_QUARTER_POINTS','1ST_QUARTER_-_TO_SCORE_20+_POINTS','TO_RECORD_20+_PTS_+_REB_+_AST','FIRST_TEAM_BASKET_SCORER']:
            self.assertFalse(self.parse(payload(kind))[0])

    def test_name_suffix_join_must_be_unique_in_current_matchup_rosters(self):
        q,issues=self.parse(payload('TO_SCORE_20+_POINTS','To Score 20+ Points',[runner('Jabari Smith')]))
        self.assertFalse(issues);self.assertEqual(q[0]['playerId'],'2');self.assertEqual(q[0]['identityJoin'],'unique-name-with-optional-suffix')
        q,issues=self.parse(payload('TO_SCORE_20+_POINTS','To Score 20+ Points',[runner('Jabari Smith')]),ROSTER+[{'id':'3','name':'Jabari Smith Sr.','team':'BOS'}])
        self.assertFalse(q);self.assertTrue(issues)

    def test_price_and_side_disagreements_are_withheld(self):
        p=payload();p['attachments']['markets']['m']['runners'][0]['winRunnerOdds']['trueOdds']['decimalOdds']['decimalOdds']=3
        self.assertIn('price mismatch',self.parse(p)[1][0])
        p=payload();p['attachments']['markets']['m']['runners'][0]['result']['type']='UNKNOWN'
        self.assertFalse(self.parse(p)[0])

    def test_event_mismatch_and_incomplete_loaded_tab_fail_without_fake_prices(self):
        p=payload();p['attachments']['events']['35928218']['inPlay']=True
        with self.assertRaises(ValueError):self.parse(p)
        p=payload();p['layout']['cards']['1']['attachmentsFullyLoaded']=False
        with self.assertRaises(ValueError):self.parse(p)
        p=payload();p['layout']['tabs']={}
        self.assertEqual(self.parse(p),([],['Market not yet offered: Player Points']))

    def test_schedule_event_join_requires_two_teams_and_unique_nearby_tipoff(self):
        self.assertEqual(fd.match_event(FIXTURE,{'a':EVENT})['eventId'],35928218)
        with self.assertRaises(ValueError):fd.match_event(FIXTURE,{'a':EVENT,'b':EVENT})
        bad={**EVENT,'openDate':'2026-10-21T19:00:00Z'}
        with self.assertRaises(ValueError):fd.match_event(FIXTURE,{'a':bad})

    def test_partial_source_failure_retains_original_quote_times_only_for_failed_market(self):
        old_quote=self.parse(payload())[0][0]
        class Fake:
            def fd(self,endpoint,**params):
                if endpoint=='competition-page':return {'attachments':{'events':{'35928218':EVENT}}},'listing'
                if params['tab']=='player-points':raise RuntimeError('temporary failure')
                return payload('3+_MADE_THREES','3+ Made Threes',[runner('Player One')],'Player Threes'),'raw'
            def json(self,url):
                team='BOS' if '/2/' in url else 'DET'
                return {'team':{'id':fd.TEAMS[team]},'athletes':[{'id':str(i),'displayName':'Player One' if i==1 else 'Other '+str(i)} for i in range(1,7)]} if team=='BOS' else {'team':{'id':8},'athletes':[{'id':str(i),'displayName':'Piston '+str(i)} for i in range(10,16)]}
        previous={'fixtures':{FIXTURE['id']:{'fixture':FIXTURE,'quotes':[old_quote]}}}
        with patch.object(fd,'schedule',return_value=([FIXTURE],[])):
            result=fd.capture(Fake(),previous,datetime(2026,10,19,tzinfo=timezone.utc))
        quotes=result['fixtures'][FIXTURE['id']]['quotes'];old=next(q for q in quotes if q['market']=='points')
        self.assertEqual(old['capturedAt'],STAMP);self.assertEqual(old['captureState'],'cached');self.assertTrue(any(q['market']=='threes' and q['captureState']=='fresh' for q in quotes))

    def test_bootstrap_reads_public_configuration_without_executing_scripts(self):
        c=fd.Client();script='var z=0;let app="publicidentifier123";let config={[o.FANDUEL]:app,[o.PREDICTS]:""};'
        with patch.object(c,'raw',side_effect=[b'<script src="/static/js/main.abc.js"></script>',script.encode()]):c.bootstrap()
        self.assertEqual(c.key,'publicidentifier123')

    def test_retry_after_http_date_is_respected_and_extended_delays_defer_collection(self):
        current=datetime(2026,10,19,tzinfo=timezone.utc)
        from datetime import timedelta
        for seconds in [10,120]:
            headers=Message();headers['Retry-After']=format_datetime(current+timedelta(seconds=seconds),usegmt=True)
            error=HTTPError('https://example.test',429,'limited',headers,None)
            delays=[];c=fd.Client(sleeper=delays.append)
            with patch.object(fd,'urlopen',side_effect=error),patch.object(fd,'utc',return_value=current):
                with self.assertRaises(RuntimeError):c.raw('https://example.test')
            self.assertEqual(delays,[10,10] if seconds==10 else [])

    def test_successfully_unposted_tabs_remove_old_offers_instead_of_reusing_old_active_prices(self):
        old=self.parse(payload())[0][0]
        class Fake:
            def fd(self,endpoint,**params):
                if endpoint=='competition-page':return {'attachments':{'events':{'35928218':EVENT}}},'listing'
                return {'attachments':{'events':{'35928218':EVENT}},'layout':{'tabs':{}}},'raw'
            def json(self,url):
                team='BOS' if '/2/' in url else 'DET'
                return {'team':{'id':fd.TEAMS[team]},'athletes':[{'id':str(i),'displayName':team+str(i)} for i in range(6)]}
        with patch.object(fd,'schedule',return_value=([FIXTURE],[])):
            result=fd.capture(Fake(),{'fixtures':{FIXTURE['id']:{'fixture':FIXTURE,'quotes':[old]}}},datetime(2026,10,19,tzinfo=timezone.utc))
        self.assertFalse(result['fixtures'][FIXTURE['id']]['quotes'])

    def test_watch_keeps_advance_odds_fresh_and_does_not_add_capture_time_to_cadence(self):
        clock={'t':0,'sleeps':[]}
        snapshot={'checkedAt':STAMP,'errors':[],'fixtures':{'401909088':{'fixture':FIXTURE,'quotes':[{'market':'points'}],'issues':[]}}}
        def capture(*args):
            clock['t']+=50
            return snapshot
        def sleep(seconds):
            clock['sleeps'].append(seconds);clock['t']+=seconds
        with patch.object(fd,'Client') as client,patch.object(fd,'capture',side_effect=capture) as captures,patch.object(fd,'publish'),patch.object(fd,'utc',return_value=datetime(2026,10,19,tzinfo=timezone.utc)),patch.object(fd.time,'monotonic',side_effect=lambda:clock['t']),patch.object(fd.time,'sleep',side_effect=sleep):
            client.return_value.json.return_value={}
            self.assertFalse(fd.run(watch=True,max_minutes=10))
        self.assertEqual(captures.call_count,2)
        self.assertEqual(clock['sleeps'],[250])

if __name__=='__main__':unittest.main()
