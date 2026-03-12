"""
FTB PbP Data Engine v3 — High-Performance Analytics Engine
=================================================================
Optimized first team basket analytics with intelligent caching and 
advanced grading algorithms for parlay generation support.

Key Improvements:
- Efficient play-by-play processing with event streaming
- Advanced player grading with weighted metrics
- Position matchup analysis
- Intelligent caching system
- Parlay generation data preparation

Author: FTB Scout Pro Analytics Engine
Version: 3.0
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, NamedTuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import hashlib

import pandas as pd

# ─── Logging Setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("ftb_engine_v3")

# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class FTBEvent:
    """Optimized FTB event structure"""
    game_id: str
    game_date: str
    team: str
    player: str
    shot_type: str
    time_seconds: int
    points: int
    is_first_basket: bool
    is_first_fg: bool
    period: int = 1

@dataclass
class PlayerMetrics:
    """Comprehensive player analytics"""
    name: str
    position: str
    team: str
    ftb_made: int
    games_started: int
    first_shot_rate: float
    shot_distribution: Dict[str, int]
    ftb_probability: float = 0.0
    grade: str = "N/A"
    matchup_score: float = 0.0
    consistency_score: float = 0.0
    last_updated: Optional[str] = None

@dataclass
class TeamMetrics:
    """Team-level analytics"""
    team: str
    games: int
    tip_win_pct: float
    first_point_pct: float
    first_fg_pct: float
    position_vulnerability: Dict[str, float]
    pace_factor: float
    offensive_efficiency: float

@dataclass
class CacheEntry:
    """Cache entry with TTL"""
    data: dict
    timestamp: datetime
    hash: str
    ttl_hours: int = 24

# ─── Constants ───────────────────────────────────────────────────────────────

SHOT_TYPES = ("layup", "dunk", "mid", "threeP", "ft", "tip", "hook")
POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Enhanced shot classification with NBA.com patterns
SHOT_PATTERNS = [
    (re.compile(r"\balley.?oop\b", re.I), "dunk"),
    (re.compile(r"\bdunk\b", re.I), "dunk"),
    (re.compile(r"\blayup\b|\blay.up\b|\bfinger.roll\b|\bcutting\b", re.I), "layup"),
    (re.compile(r"\bdriving\b.*\blayup\b", re.I), "layup"),
    (re.compile(r"\b(hook)\b", re.I), "hook"),
    (re.compile(r"\btip.?in\b|\btip.?shot\b|\btip\b", re.I), "tip"),
    (re.compile(r"\bfree.throw\b", re.I), "ft"),
    (re.compile(r"3pt\b|3-point|\bthree.point|\bthree pt\b|3PT Jump", re.I), "threeP"),
    (re.compile(r"three point jumper|three point shot", re.I), "threeP"),
    (re.compile(r"\d+-foot three", re.I), "threeP"),
    (re.compile(r"\bfloating\b|\bstep.back\b|\bfadeaway\b|\bpull.up\b|\brunning\b", re.I), "mid"),
    (re.compile(r"\bjumper\b|\bjump.?shot\b", re.I), "mid"),
]

# Position-based weights for matchup analysis
POSITION_MATCHUP_WEIGHTS = {
    ("PG", "PG"): 1.0, ("PG", "SG"): 0.9, ("PG", "SF"): 0.7, ("PG", "PF"): 0.5, ("PG", "C"): 0.3,
    ("SG", "PG"): 0.9, ("SG", "SG"): 1.0, ("SG", "SF"): 0.8, ("SG", "PF"): 0.6, ("SG", "C"): 0.4,
    ("SF", "PG"): 0.7, ("SF", "SG"): 0.8, ("SF", "SF"): 1.0, ("SF", "PF"): 0.9, ("SF", "C"): 0.6,
    ("PF", "PG"): 0.5, ("PF", "SG"): 0.6, ("PF", "SF"): 0.9, ("PF", "PF"): 1.0, ("PF", "C"): 0.8,
    ("C", "PG"): 0.3, ("C", "SG"): 0.4, ("C", "SF"): 0.6, ("C", "PF"): 0.8, ("C", "C"): 1.0,
}

# ─── Core Engine Class ─────────────────────────────────────────────────────────

class FTBAnalyticsEngine:
    """High-performance FTB analytics engine with caching"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache: Dict[str, CacheEntry] = {}
        self.player_metrics: Dict[str, PlayerMetrics] = {}
        self.team_metrics: Dict[str, TeamMetrics] = {}
        self.position_data: Dict[str, Dict[str, int]] = {}
        
        # Load cached data on initialization
        self._load_cache()
    
    def _generate_hash(self, data: dict) -> str:
        """Generate SHA-256 hash for data integrity"""
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    
    def _is_cache_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid"""
        return datetime.now() - entry.timestamp < timedelta(hours=entry.ttl_hours)
    
    def _load_cache(self) -> None:
        """Load all valid cache entries"""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Convert timestamp back to datetime
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                
                entry = CacheEntry(**data)
                
                if self._is_cache_valid(entry):
                    self.cache[cache_file.stem] = entry
                    log.info(f"Loaded cache: {cache_file.stem}")
                else:
                    cache_file.unlink()  # Remove expired cache
                    
            except Exception as e:
                log.warning(f"Failed to load cache {cache_file}: {e}")
    
    def _save_cache(self, key: str, data: dict, ttl_hours: int = 24) -> None:
        """Save data to cache with TTL"""
        entry = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            hash=self._generate_hash(data),
            ttl_hours=ttl_hours
        )
        
        self.cache[key] = entry
        
        cache_file = self.cache_dir / f"{key}.json"
        with open(cache_file, 'w') as f:
            # Convert datetime to string for JSON serialization
            cache_dict = asdict(entry)
            cache_dict['timestamp'] = entry.timestamp.isoformat()
            json.dump(cache_dict, f, indent=2)
    
    def classify_shot_type(self, description: str) -> str:
        """Efficient shot type classification"""
        description = description.lower().strip()
        
        for pattern, shot_type in SHOT_PATTERNS:
            if pattern.search(description):
                return shot_type
        
        # Default classification based on keywords
        if any(word in description for word in ['jumper', 'jump', 'shot']):
            return "mid"
        return "mid"  # Default to mid-range
    
    def process_play_by_play(self, pbp_data: List[Dict]) -> List[FTBEvent]:
        """Optimized play-by-play processing for FTB events"""
        events = []
        game_first_baskets = {}  # Track first basket per game
        game_first_fgs = {}      # Track first FG per game
        
        for play in pbp_data:
            # Early filtering - only process scoring plays
            if not self._is_scoring_play(play):
                continue
            
            game_id = play.get('GAME_ID', '')
            if not game_id:
                continue
            
            # Initialize game tracking if needed
            if game_id not in game_first_baskets:
                game_first_baskets[game_id] = None
                game_first_fgs[game_id] = None
            
            event = self._parse_ftb_event(play, game_first_baskets, game_first_fgs)
            if event:
                events.append(event)
        
        log.info(f"Processed {len(events)} FTB events from {len(pbp_data)} plays")
        return events
    
    def _is_scoring_play(self, play: Dict) -> bool:
        """Quick filter for scoring plays"""
        return (
            play.get('HOME_POINTS', 0) > 0 or 
            play.get('AWAY_POINTS', 0) > 0 or
            'SCORE' in play.get('EVENT_TYPE', '').upper()
        )
    
    def _parse_ftb_event(self, play: Dict, game_first_baskets: Dict, game_first_fgs: Dict) -> Optional[FTBEvent]:
        """Parse individual FTB event with optimized logic"""
        game_id = play['GAME_ID']
        
        # Determine scoring team and player
        if play.get('HOME_POINTS', 0) > 0:
            team, player, points = play['HOME_TEAM'], play.get('HOME_FIRST_SCORER'), play['HOME_POINTS']
            shot_desc = play.get('HOME_SHOT_DESC', '')
            time_str = play.get('HOME_TIME', '0:00')
        elif play.get('AWAY_POINTS', 0) > 0:
            team, player, points = play['AWAY_TEAM'], play.get('AWAY_FIRST_SCORER'), play['AWAY_POINTS']
            shot_desc = play.get('AWAY_SHOT_DESC', '')
            time_str = play.get('AWAY_TIME', '0:00')
        else:
            return None
        
        if not player or not team:
            return None
        
        # Parse time
        time_seconds = self._parse_time(time_str)
        
        # Classify shot type
        shot_type = self.classify_shot_type(shot_desc)
        
        # Determine if this is first basket/FG
        is_first_basket = game_first_baskets[game_id] is None
        is_first_fg = is_first_basket and points > 0  # FTs don't count as FG
        
        if is_first_basket:
            game_first_baskets[game_id] = player
        if is_first_fg and game_first_fgs[game_id] is None:
            game_first_fgs[game_id] = player
        
        return FTBEvent(
            game_id=game_id,
            game_date=play.get('GAME_DATE', ''),
            team=team,
            player=player,
            shot_type=shot_type,
            time_seconds=time_seconds,
            points=points,
            is_first_basket=is_first_basket,
            is_first_fg=is_first_fg,
            period=int(play.get('PERIOD', 1))
        )
    
    def _parse_time(self, time_str: str) -> int:
        """Parse MM:SS format to seconds"""
        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
        except:
            pass
        return 0
    
    def calculate_player_grades(self, players: Dict[str, PlayerMetrics]) -> Dict[str, PlayerMetrics]:
        """Advanced player grading with weighted metrics"""
        graded_players = {}
        
        # Calculate statistical baselines
        ftb_rates = [p.ftb_made / max(p.games_started, 1) for p in players.values()]
        avg_ftb_rate = sum(ftb_rates) / len(ftb_rates) if ftb_rates else 0
        std_ftb_rate = (sum((x - avg_ftb_rate) ** 2 for x in ftb_rates) / len(ftb_rates)) ** 0.5 if ftb_rates else 1
        
        for name, player in players.items():
            # Core metrics
            ftb_rate = player.ftb_made / max(player.games_started, 1)
            first_shot_rate = player.first_shot_rate
            
            # Position-based scoring tendency
            position_score = self._calculate_position_score(player.position, player.shot_distribution)
            
            # Consistency score (based on shot distribution variance)
            consistency = self._calculate_consistency(player.shot_distribution)
            
            # Composite score (weighted)
            composite_score = (
                0.4 * self._normalize_score(ftb_rate, avg_ftb_rate, std_ftb_rate) +
                0.3 * first_shot_rate +
                0.2 * position_score +
                0.1 * consistency
            )
            
            # Assign grade
            grade = self._score_to_grade(composite_score)
            
            # Update player with calculated metrics
            player.ftb_probability = composite_score
            player.grade = grade
            player.consistency_score = consistency
            player.last_updated = datetime.now().isoformat()
            
            graded_players[name] = player
        
        log.info(f"Graded {len(graded_players)} players")
        return graded_players
    
    def _normalize_score(self, value: float, mean: float, std: float) -> float:
        """Normalize score to 0-1 range"""
        if std == 0:
            return 0.5
        z_score = (value - mean) / std
        return max(0, min(1, (z_score + 3) / 6))  # Clamp to 0-1
    
    def _calculate_position_score(self, position: str, shot_dist: Dict[str, int]) -> float:
        """Calculate position-based scoring advantage"""
        total_shots = sum(shot_dist.values())
        if total_shots == 0:
            return 0.0
        
        # Position-specific scoring patterns
        position_weights = {
            "PG": {"threeP": 0.4, "mid": 0.3, "layup": 0.2, "ft": 0.1},
            "SG": {"threeP": 0.35, "mid": 0.25, "layup": 0.25, "ft": 0.15},
            "SF": {"threeP": 0.3, "mid": 0.25, "layup": 0.3, "dunk": 0.15},
            "PF": {"mid": 0.3, "layup": 0.25, "dunk": 0.25, "threeP": 0.2},
            "C": {"layup": 0.35, "dunk": 0.35, "mid": 0.2, "hook": 0.1},
        }
        
        weights = position_weights.get(position, position_weights["SF"])
        score = 0.0
        
        for shot_type, weight in weights.items():
            actual_pct = shot_dist.get(shot_type, 0) / total_shots
            score += weight * actual_pct
        
        return min(1.0, score)
    
    def _calculate_consistency(self, shot_dist: Dict[str, int]) -> float:
        """Calculate shot consistency (inverse of variance)"""
        total_shots = sum(shot_dist.values())
        if total_shots < 5:  # Not enough data
            return 0.0
        
        # Calculate variance in shot distribution
        percentages = [count / total_shots for count in shot_dist.values()]
        mean_pct = 1.0 / len(percentages)
        variance = sum((p - mean_pct) ** 2 for p in percentages)
        
        # Consistency is inverse of variance (normalized)
        consistency = 1.0 / (1.0 + variance)
        return consistency
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade"""
        if score >= 0.9: return "A+"
        elif score >= 0.85: return "A"
        elif score >= 0.8: return "A-"
        elif score >= 0.75: return "B+"
        elif score >= 0.7: return "B"
        elif score >= 0.65: return "B-"
        elif score >= 0.6: return "C+"
        elif score >= 0.55: return "C"
        elif score >= 0.5: return "C-"
        elif score >= 0.4: return "D"
        else: return "F"
    
    def calculate_position_matchups(self, home_team: str, away_team: str, 
                                 home_players: List[PlayerMetrics], 
                                 away_players: List[PlayerMetrics]) -> Dict[str, float]:
        """Calculate position matchup advantages for parlay generation"""
        matchups = {}
        
        # Group players by position
        home_by_pos = {pos: [p for p in home_players if p.position == pos] for pos in POSITIONS}
        away_by_pos = {pos: [p for p in away_players if p.position == pos] for pos in POSITIONS}
        
        for pos in POSITIONS:
            home_players_pos = home_by_pos[pos]
            away_players_pos = away_by_pos[pos]
            
            if not home_players_pos or not away_players_pos:
                continue
            
            # Calculate average FTB probability for each position
            home_avg = sum(p.ftb_probability for p in home_players_pos) / len(home_players_pos)
            away_avg = sum(p.ftb_probability for p in away_players_pos) / len(away_players_pos)
            
            # Apply matchup weights
            matchup_weight = POSITION_MATCHUP_WEIGHTS.get((pos, pos), 1.0)
            matchup_score = (home_avg - away_avg) * matchup_weight
            
            matchups[f"{home_team}_{pos}_vs_{away_team}_{pos}"] = matchup_score
        
        return matchups
    
    def generate_parlay_data(self, game_players: Dict[str, List[PlayerMetrics]]) -> Dict:
        """Generate structured data for parlay generation"""
        parlay_data = {
            "timestamp": datetime.now().isoformat(),
            "games": {},
            "top_candidates": [],
            "position_matchups": {},
            "team_tendencies": {}
        }
        
        all_players = []
        for game_id, players in game_players.items():
            # Sort by FTB probability
            sorted_players = sorted(players, key=lambda p: p.ftb_probability, reverse=True)
            
            game_data = {
                "game_id": game_id,
                "top_candidates": [
                    {
                        "name": p.name,
                        "position": p.position,
                        "team": p.team,
                        "ftb_probability": p.ftb_probability,
                        "grade": p.grade,
                        "consistency": p.consistency_score,
                        "shot_distribution": p.shot_distribution
                    }
                    for p in sorted_players[:5]  # Top 5 per game
                ],
                "team_analysis": self._analyze_team_tendencies(players)
            }
            
            parlay_data["games"][game_id] = game_data
            all_players.extend(players)
        
        # Global top candidates
        global_top = sorted(all_players, key=lambda p: p.ftb_probability, reverse=True)[:20]
        parlay_data["top_candidates"] = [
            {
                "name": p.name, "position": p.position, "team": p.team,
                "ftb_probability": p.ftb_probability, "grade": p.grade,
                "consistency": p.consistency_score
            }
            for p in global_top
        ]
        
        return parlay_data
    
    def _analyze_team_tendencies(self, players: List[PlayerMetrics]) -> Dict:
        """Analyze team-level FTB tendencies"""
        if not players:
            return {}
        
        # Aggregate shot distributions
        team_shots = Counter()
        total_ftb = sum(p.ftb_made for p in players)
        
        for player in players:
            for shot_type, count in player.shot_distribution.items():
                team_shots[shot_type] += count
        
        # Calculate percentages
        total_shots = sum(team_shots.values())
        shot_percentages = {shot: count/total_shots for shot, count in team_shots.items()}
        
        return {
            "total_ftb": total_ftb,
            "shot_distribution": shot_percentages,
            "primary_positions": Counter(p.position for p in players),
            "average_grade": self._calculate_average_grade(players)
        }
    
    def _calculate_average_grade(self, players: List[PlayerMetrics]) -> str:
        """Calculate average team grade"""
        if not players:
            return "N/A"
        
        grade_values = {"A+": 4.0, "A": 3.7, "A-": 3.3, "B+": 3.0, "B": 2.7, "B-": 2.3,
                       "C+": 2.0, "C": 1.7, "C-": 1.3, "D": 1.0, "F": 0.0}
        
        total_value = sum(grade_values.get(p.grade, 0) for p in players)
        avg_value = total_value / len(players)
        
        # Convert back to grade
        for grade, value in sorted(grade_values.items(), key=lambda x: x[1], reverse=True):
            if avg_value >= value:
                return grade
        
        return "F"

# ─── Utility Functions ─────────────────────────────────────────────────────────

def load_roster_data(roster_path: str) -> Dict[str, Dict]:
    """Load and normalize roster data"""
    with open(roster_path, 'r', encoding='utf-8') as f:
        roster = json.load(f)
    
    player_map = {}
    for player in roster.get('players', []):
        player_map[player['full_name']] = {
            'position': player['position'],
            'team': player['primary_team']
        }
    
    log.info(f"Loaded {len(player_map)} players from roster")
    return player_map

def export_results(engine: FTBAnalyticsEngine, output_dir: str) -> None:
    """Export engine results in multiple formats"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Export player metrics
    players_data = {name: asdict(player) for name, player in engine.player_metrics.items()}
    with open(output_path / "player_metrics_v3.json", 'w') as f:
        json.dump(players_data, f, indent=2)
    
    # Export team metrics
    teams_data = {team: asdict(metrics) for team, metrics in engine.team_metrics.items()}
    with open(output_path / "team_metrics_v3.json", 'w') as f:
        json.dump(teams_data, f, indent=2)
    
    # Export parlay data
    games_data = {}
    for team, players in engine.player_metrics.items():
        game_id = f"{team}_{datetime.now().strftime('%Y%m%d')}"
        if game_id not in games_data:
            games_data[game_id] = []
        games_data[game_id].append(players)
    
    parlay_data = engine.generate_parlay_data(games_data)
    with open(output_path / "parlay_data_v3.json", 'w') as f:
        json.dump(parlay_data, f, indent=2)
    
    log.info(f"Exported results to {output_dir}")

# ─── Main Execution ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example usage
    engine = FTBAnalyticsEngine()
    
    # Load roster data
    roster_data = load_roster_data("player_roster.json")
    
    log.info("FTB Analytics Engine v3 initialized successfully")
    log.info(f"Cache directory: {engine.cache_dir}")
    log.info(f"Cached entries: {len(engine.cache)}")
