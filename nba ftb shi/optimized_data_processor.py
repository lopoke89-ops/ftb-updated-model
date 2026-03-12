"""
Optimized Data Processor for FTB Analytics
==========================================
High-performance processor for NBA_First_Basket_2025-26.xlsx data
with intelligent caching and position resolution.

Key Features:
- Streamlined Excel processing
- Automatic position resolution
- Missing data handling
- Performance monitoring
- Cache integration with v3 engine
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass, asdict
import pandas as pd

from ftb_engine_v3 import FTBAnalyticsEngine, PlayerMetrics, TeamMetrics, load_roster_data

# ─── Logging Setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("data_processor")

# ─── Data Processing Configuration ───────────────────────────────────────────

@dataclass
class ProcessingConfig:
    """Configuration for data processing"""
    min_games_started: int = 3
    min_ftb_for_display: int = 1
    cache_ttl_hours: int = 24
    enable_performance_monitoring: bool = True
    batch_size: int = 1000
    allow_dummy_data: bool = False
    
    # Position resolution settings
    fallback_position: str = "SF"  # Default position if unknown
    position_confidence_threshold: float = 0.7

class PerformanceMonitor:
    """Monitor processing performance"""
    
    def __init__(self):
        self.start_time = None
        self.checkpoints = {}
    
    def start(self):
        """Start monitoring"""
        self.start_time = time.time()
        log.info("🚀 Processing started")
    
    def checkpoint(self, name: str):
        """Record checkpoint"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.checkpoints[name] = elapsed
            log.info(f"⏱️  {name}: {elapsed:.2f}s")
    
    def finish(self):
        """Finish monitoring and report"""
        if self.start_time:
            total_time = time.time() - self.start_time
            log.info(f"✅ Processing completed in {total_time:.2f}s")
            
            if len(self.checkpoints) > 1:
                log.info("📊 Performance breakdown:")
                for i, (name, elapsed) in enumerate(self.checkpoints.items()):
                    pct = (elapsed / total_time) * 100
                    log.info(f"   {name}: {elapsed:.2f}s ({pct:.1f}%)")

class OptimizedDataProcessor:
    """High-performance data processor with caching and optimization"""
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.engine = FTBAnalyticsEngine()
        self.roster_data = {}
        self.performance = PerformanceMonitor()
        
        # Load roster data for position resolution
        self._load_roster_data()
    
    def _load_roster_data(self) -> None:
        """Load roster data for position resolution"""
        roster_path = Path("player_roster.json")
        if roster_path.exists():
            try:
                with open(roster_path, 'r', encoding='utf-8') as f:
                    roster = json.load(f)
                
                self.roster_data = {}
                for player in roster.get('players', []):
                    self.roster_data[player['full_name']] = {
                        'position': player['position'],
                        'team': player['primary_team']
                    }
                
                log.info(f"📋 Loaded roster data for {len(self.roster_data)} players")
            except Exception as e:
                log.warning(f"⚠️  Failed to load roster data: {e}")
                self.roster_data = {}
        else:
            log.warning("⚠️  Roster data not found - position resolution will be limited")
            self.roster_data = {}
    
    def process_excel_data(self, excel_path: str) -> Tuple[Dict[str, PlayerMetrics], Dict[str, TeamMetrics]]:
        """Process Excel data with optimization and caching"""
        self.performance.start()
        
        # Check cache first
        cache_key = f"excel_processed_{Path(excel_path).stem}"
        cached_result = self._load_from_cache(cache_key)
        
        if cached_result:
            log.info("📦 Using cached processed data")
            self.performance.finish()
            return cached_result
        
        # Process fresh data
        log.info(f"📊 Processing Excel data: {excel_path}")
        
        # Load Excel with optimized settings
        df = self._load_excel_optimized(excel_path)
        self.performance.checkpoint("Excel loading")
        
        # Process player data
        player_metrics = self._process_players(df)
        self.performance.checkpoint("Player processing")
        
        # Process team data  
        team_metrics = self._process_teams(df)
        self.performance.checkpoint("Team processing")
        
        # Apply advanced grading
        player_metrics = self.engine.calculate_player_grades(player_metrics)
        self.performance.checkpoint("Grading")
        
        # Cache results
        result = (player_metrics, team_metrics)
        self._save_to_cache(cache_key, result)
        
        self.performance.finish()
        return result
    
    def _load_excel_optimized(self, excel_path: str) -> pd.DataFrame:
        """Load Excel with optimization"""
        log.info("📂 Loading Excel file...")
        
        # Load only necessary columns and rows
        usecols = [
            "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM",
            "HOME_FIRST_SCORER", "HOME_SHOT_DESC", "HOME_POINTS", "HOME_TIME",
            "AWAY_FIRST_SCORER", "AWAY_SHOT_DESC", "AWAY_POINTS", "AWAY_TIME"
        ]
        
        try:
            df = pd.read_excel(excel_path, sheet_name="First Baskets", usecols=usecols, engine='openpyxl')
            log.info(f"📈 Loaded {len(df)} records")
            
            # Data validation
            self._validate_dataframe(df)
            
            return df
            
        except Exception as e:
            log.error(f"❌ Failed to load Excel: {e}")
            if self.config.allow_dummy_data:
                log.warning("🔄 Dummy data enabled - creating sample dataset")
                return self._create_dummy_data()
            raise
    
    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate loaded dataframe"""
        required_cols = ["GAME_ID", "HOME_TEAM", "AWAY_TEAM", "HOME_FIRST_SCORER", "AWAY_FIRST_SCORER"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Check for empty data
        if df.empty:
            raise ValueError("Excel file contains no data")
        
        # Basic data quality checks
        null_games = df['GAME_ID'].isnull().sum()
        if null_games > 0:
            log.warning(f"⚠️  Found {null_games} records with null GAME_ID")
        
        log.info("✅ Data validation passed")
    
    def _create_dummy_data(self) -> pd.DataFrame:
        """Create dummy data for testing when Excel is unavailable"""
        import random
        from datetime import datetime, timedelta
        
        teams = ["ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW"]
        players = ["Luka Doncic", "LeBron James", "Stephen Curry", "Kevin Durant", "Giannis Antetokounmpo"]
        shot_types = ["layup", "dunk", "mid", "threeP"]
        
        dummy_records = []
        game_id = 1
        
        for i in range(100):  # Create 100 dummy records
            home_team = random.choice(teams)
            away_team = random.choice([t for t in teams if t != home_team])
            game_date = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
            
            # Home team first basket
            home_player = random.choice(players)
            home_shot = random.choice(shot_types)
            home_points = random.choice([2, 3])
            home_time = f"{random.randint(0, 11)}:{random.randint(0, 59):02d}"
            
            # Away team first basket  
            away_player = random.choice(players)
            away_shot = random.choice(shot_types)
            away_points = random.choice([2, 3])
            away_time = f"{random.randint(0, 11)}:{random.randint(0, 59):02d}"
            
            dummy_records.append({
                "GAME_ID": f"GAME_{game_id:05d}",
                "GAME_DATE": game_date,
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_FIRST_SCORER": home_player,
                "HOME_SHOT_DESC": home_shot,
                "HOME_POINTS": home_points,
                "HOME_TIME": home_time,
                "AWAY_FIRST_SCORER": away_player,
                "AWAY_SHOT_DESC": away_shot,
                "AWAY_POINTS": away_points,
                "AWAY_TIME": away_time
            })
            
            game_id += 1
        
        df = pd.DataFrame(dummy_records)
        log.info(f"📊 Created {len(df)} dummy records for testing")
        return df
    
    def _process_players(self, df: pd.DataFrame) -> Dict[str, PlayerMetrics]:
        """Process player data with optimization and position resolution"""
        log.info("👤 Processing player data...")
        
        # Extract unique players with their teams
        home_players = df[['HOME_FIRST_SCORER', 'HOME_TEAM']].dropna()
        away_players = df[['AWAY_FIRST_SCORER', 'AWAY_TEAM']].dropna()
        
        # Combine and deduplicate
        all_players = []
        for _, row in home_players.iterrows():
            all_players.append((row['HOME_FIRST_SCORER'], row['HOME_TEAM']))
        for _, row in away_players.iterrows():
            all_players.append((row['AWAY_FIRST_SCORER'], row['AWAY_TEAM']))
        
        # Remove duplicates and count
        unique_players = list(set(all_players))
        log.info(f"📊 Found {len(unique_players)} unique players")
        
        # Process each player
        player_metrics = {}
        for player_name, team in unique_players:
            metrics = self._calculate_player_metrics(df, player_name, team)
            if metrics:
                player_metrics[player_name] = metrics
        
        log.info(f"✅ Processed {len(player_metrics)} players with valid metrics")
        return player_metrics
    
    def _calculate_player_metrics(self, df: pd.DataFrame, player_name: str, team: str) -> Optional[PlayerMetrics]:
        """Calculate metrics for individual player"""
        # Filter data for this player
        home_mask = (df['HOME_FIRST_SCORER'] == player_name) & (df['HOME_TEAM'] == team)
        away_mask = (df['AWAY_FIRST_SCORER'] == player_name) & (df['AWAY_TEAM'] == team)
        
        player_data = pd.concat([df[home_mask], df[away_mask]])
        
        if player_data.empty:
            return None
        
        # Calculate basic metrics
        ftb_made = len(player_data)
        
        # Estimate games started (simplified - should be enhanced with actual data)
        unique_games = player_data['GAME_ID'].nunique()
        games_started = max(unique_games, self.config.min_games_started)
        
        first_shot_rate = ftb_made / max(games_started, 1)
        
        # Process shot distribution
        shot_distribution = self._calculate_shot_distribution(player_data)
        
        # Resolve position
        position = self._resolve_player_position(player_name, team)
        
        return PlayerMetrics(
            name=player_name,
            position=position,
            team=team,
            ftb_made=ftb_made,
            games_started=games_started,
            first_shot_rate=first_shot_rate,
            shot_distribution=shot_distribution,
            last_updated=datetime.now().isoformat()
        )
    
    def _calculate_shot_distribution(self, player_data: pd.DataFrame) -> Dict[str, int]:
        """Calculate shot type distribution for player"""
        shot_counts = {
            "layup": 0, "dunk": 0, "mid": 0, "threeP": 0, 
            "ft": 0, "tip": 0, "hook": 0
        }
        
        # Process home team shots
        home_shots = player_data['HOME_SHOT_DESC'].dropna()
        for shot_desc in home_shots:
            shot_type = self.engine.classify_shot_type(str(shot_desc))
            if shot_type in shot_counts:
                shot_counts[shot_type] += 1
        
        # Process away team shots
        away_shots = player_data['AWAY_SHOT_DESC'].dropna()
        for shot_desc in away_shots:
            shot_type = self.engine.classify_shot_type(str(shot_desc))
            if shot_type in shot_counts:
                shot_counts[shot_type] += 1
        
        return shot_counts
    
    def _resolve_player_position(self, player_name: str, team: str) -> str:
        """Resolve player position with fallback strategies"""
        # Strategy 1: Check roster data
        if player_name in self.roster_data:
            position = self.roster_data[player_name]['position']
            if position in ["PG", "SG", "SF", "PF", "C"]:
                return position
        
        # Strategy 2: Try name-based heuristics (limited implementation)
        position = self._guess_position_from_name(player_name)
        if position:
            return position
        
        # Strategy 3: Use fallback
        log.debug(f"🔍 Using fallback position for {player_name}: {self.config.fallback_position}")
        return self.config.fallback_position
    
    def _guess_position_from_name(self, player_name: str) -> Optional[str]:
        """Very basic position guessing from name patterns"""
        # This is a placeholder - could be enhanced with external data
        # For now, return None to use fallback
        return None
    
    def _process_teams(self, df: pd.DataFrame) -> Dict[str, TeamMetrics]:
        """Process team-level metrics"""
        log.info("🏢 Processing team data...")
        
        # Get all unique teams
        home_teams = df['HOME_TEAM'].unique()
        away_teams = df['AWAY_TEAM'].unique()
        all_teams = set(home_teams) | set(away_teams)
        
        team_metrics = {}
        
        for team in all_teams:
            metrics = self._calculate_team_metrics(df, team)
            if metrics:
                team_metrics[team] = metrics
        
        log.info(f"✅ Processed {len(team_metrics)} teams")
        return team_metrics
    
    def _calculate_team_metrics(self, df: pd.DataFrame, team: str) -> Optional[TeamMetrics]:
        """Calculate metrics for individual team"""
        # Filter team games
        home_games = df[df['HOME_TEAM'] == team]
        away_games = df[df['AWAY_TEAM'] == team]
        
        total_games = len(home_games) + len(away_games)
        
        if total_games == 0:
            return None
        
        # Calculate tip win percentage (simplified - needs actual tip data)
        tip_wins = len(home_games)  # Assume home team wins tip (placeholder)
        tip_win_pct = tip_wins / total_games
        
        # Calculate first point percentage
        first_points = len(home_games[home_games['HOME_POINTS'].notna()]) + \
                      len(away_games[away_games['AWAY_POINTS'].notna()])
        first_point_pct = first_points / total_games
        
        # Calculate first FG percentage (excluding free throws)
        home_fgs = home_games[(home_games['HOME_POINTS'].notna()) & (home_games['HOME_POINTS'] > 1)]
        away_fgs = away_games[(away_games['AWAY_POINTS'].notna()) & (away_games['AWAY_POINTS'] > 1)]
        first_fgs = len(home_fgs) + len(away_fgs)
        first_fg_pct = first_fgs / total_games
        
        # Position vulnerability (placeholder - needs more sophisticated analysis)
        position_vulnerability = {
            "PG": 0.2, "SG": 0.2, "SF": 0.2, "PF": 0.2, "C": 0.2
        }
        
        return TeamMetrics(
            team=team,
            games=total_games,
            tip_win_pct=tip_win_pct,
            first_point_pct=first_point_pct,
            first_fg_pct=first_fg_pct,
            position_vulnerability=position_vulnerability,
            pace_factor=1.0,  # Placeholder
            offensive_efficiency=1.0  # Placeholder
        )
    
    def _load_from_cache(self, cache_key: str) -> Optional[Tuple[Dict[str, PlayerMetrics], Dict[str, TeamMetrics]]]:
        """Load processed data from cache"""
        if cache_key in self.engine.cache:
            entry = self.engine.cache[cache_key]
            if self.engine._is_cache_valid(entry):
                try:
                    data = entry.data
                    players = {name: PlayerMetrics(**metrics) for name, metrics in data['players'].items()}
                    teams = {team: TeamMetrics(**metrics) for team, metrics in data['teams'].items()}
                    return players, teams
                except Exception as e:
                    log.warning(f"Cache loading failed: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, result: Tuple[Dict[str, PlayerMetrics], Dict[str, TeamMetrics]]) -> None:
        """Save processed data to cache"""
        players, teams = result
        
        cache_data = {
            'players': {name: self._serialize_player(player) for name, player in players.items()},
            'teams': {team: self._serialize_team(team_metrics) for team, team_metrics in teams.items()},
            'processed_at': datetime.now().isoformat(),
            'config': asdict(self.config)
        }
        
        self.engine._save_cache(cache_key, cache_data, self.config.cache_ttl_hours)
        log.info(f"💾 Cached processed data: {cache_key}")
    
    def export_optimized_data(self, players: Dict[str, PlayerMetrics], 
                             teams: Dict[str, TeamMetrics], 
                             output_dir: str) -> None:
        """Export data in optimized formats for the web application"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Export in legacy format for compatibility
        self._export_legacy_format(players, teams, output_path)
        
        # Export enhanced format
        self._export_enhanced_format(players, teams, output_path)
        
        # Export parlay-ready data
        self._export_parlay_data(players, output_path)
        
        log.info(f"📤 Exported optimized data to {output_dir}")
    
    def _export_legacy_format(self, players: Dict[str, PlayerMetrics], 
                            teams: Dict[str, TeamMetrics], 
                            output_path: Path) -> None:
        """Export in format compatible with existing web app"""
        player_ftb = {}
        for name, player in players.items():
            if player.ftb_made >= self.config.min_ftb_for_display:
                player_ftb[name] = {
                    "ftbMade": player.ftb_made,
                    "gamesStarted": player.games_started,
                    "firstShotRate": player.first_shot_rate,
                    "shots": player.shot_distribution,
                    "position": player.position,
                    "team": player.team,
                    # Enhanced fields
                    "ftbProbability": player.ftb_probability,
                    "grade": player.grade,
                    "consistency": player.consistency_score
                }
        
        team_stats = {}
        for team, metrics in teams.items():
            team_stats[team] = {
                "games": metrics.games,
                "tipPct": round(metrics.tip_win_pct * 100, 1),
                "firstPointPct": round(metrics.first_point_pct * 100, 1),
                "firstFGPct": round(metrics.first_fg_pct * 100, 1),
                # Enhanced fields
                "paceFactor": metrics.pace_factor,
                "offensiveEfficiency": metrics.offensive_efficiency,
                "positionVulnerability": metrics.position_vulnerability
            }
        
        # Main output file
        output_data = {
            "playerFtb": player_ftb,
            "teamStats": team_stats,
            "generated": datetime.now().isoformat(),
            "version": "v3_optimized",
            "totalPlayers": len(player_ftb),
            "totalTeams": len(team_stats)
        }
        
        with open(output_path / "ftb_data_output_v3.json", 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # JavaScript patch for HTML
        js_content = f"// AUTO-GENERATED by optimized_data_processor.py\n"
        js_content += f"// Generated: {datetime.now().isoformat()}\n"
        js_content += f"const SEASON_FTB_DATA_V3 = {json.dumps(player_ftb, indent=2)};\n"
        
        with open(output_path / "season_ftb_patch_v3.js", 'w') as f:
            f.write(js_content)
    
    def _export_enhanced_format(self, players: Dict[str, PlayerMetrics], 
                             teams: Dict[str, TeamMetrics], 
                             output_path: Path) -> None:
        """Export enhanced format with all analytics"""
        enhanced_data = {
            "metadata": {
                "version": "v3.0",
                "generated": datetime.now().isoformat(),
                "config": asdict(self.config),
                "performance": self.performance.checkpoints
            },
            "players": {name: self._serialize_player(player) for name, player in players.items()},
            "teams": {team: self._serialize_team(team_metrics) for team, team_metrics in teams.items()},
            "analytics": {
                "grade_distribution": self._calculate_grade_distribution(players),
                "position_analysis": self._analyze_positions(players),
                "team_rankings": self._rank_teams(teams)
            }
        }
        
        with open(output_path / "enhanced_analytics_v3.json", 'w') as f:
            json.dump(enhanced_data, f, indent=2)
    
    def _serialize_player(self, player: PlayerMetrics) -> dict:
        """Serialize PlayerMetrics to JSON-compatible dict"""
        return {
            "name": player.name,
            "position": player.position,
            "team": player.team,
            "ftb_made": player.ftb_made,
            "games_started": player.games_started,
            "first_shot_rate": player.first_shot_rate,
            "shot_distribution": player.shot_distribution,
            "ftb_probability": player.ftb_probability,
            "grade": player.grade,
            "matchup_score": player.matchup_score,
            "consistency_score": player.consistency_score,
            "last_updated": player.last_updated
        }
    
    def _serialize_team(self, team: TeamMetrics) -> dict:
        """Serialize TeamMetrics to JSON-compatible dict"""
        return {
            "team": team.team,
            "games": team.games,
            "tip_win_pct": team.tip_win_pct,
            "first_point_pct": team.first_point_pct,
            "first_fg_pct": team.first_fg_pct,
            "position_vulnerability": team.position_vulnerability,
            "pace_factor": team.pace_factor,
            "offensive_efficiency": team.offensive_efficiency
        }
    
    def _export_parlay_data(self, players: Dict[str, PlayerMetrics], output_path: Path) -> None:
        """Export data optimized for parlay generation"""
        # Group players by team for matchup analysis
        team_players = {}
        for player in players.values():
            if player.team not in team_players:
                team_players[player.team] = []
            team_players[player.team].append(player)
        
        # Generate parlay data
        parlay_data = self.engine.generate_parlay_data(team_players)
        
        with open(output_path / "parlay_ready_v3.json", 'w') as f:
            json.dump(parlay_data, f, indent=2)
    
    def _calculate_grade_distribution(self, players: Dict[str, PlayerMetrics]) -> Dict[str, int]:
        """Calculate distribution of player grades"""
        grades = [player.grade for player in players.values()]
        return dict(pd.Series(grades).value_counts().to_dict())
    
    def _analyze_positions(self, players: Dict[str, PlayerMetrics]) -> Dict[str, Dict]:
        """Analyze player positions and performance"""
        position_analysis = {}
        
        for position in ["PG", "SG", "SF", "PF", "C"]:
            pos_players = [p for p in players.values() if p.position == position]
            if pos_players:
                position_analysis[position] = {
                    "count": len(pos_players),
                    "avg_ftb_probability": sum(p.ftb_probability for p in pos_players) / len(pos_players),
                    "avg_consistency": sum(p.consistency_score for p in pos_players) / len(pos_players),
                    "top_players": [self._serialize_player(p) for p in sorted(pos_players, key=lambda p: p.ftb_probability, reverse=True)[:3]]
                }
        
        return position_analysis
    
    def _rank_teams(self, teams: Dict[str, TeamMetrics]) -> List[Tuple[str, float]]:
        """Rank teams by offensive efficiency"""
        team_rankings = [(team, metrics.offensive_efficiency) for team, metrics in teams.items()]
        return sorted(team_rankings, key=lambda x: x[1], reverse=True)

# ─── Main Execution ─────────────────────────────────────────────────────────

def main():
    """Main processing function"""
    config = ProcessingConfig(
        min_games_started=3,
        min_ftb_for_display=1,
        cache_ttl_hours=24,
        enable_performance_monitoring=True,
        allow_dummy_data=False
    )
    
    processor = OptimizedDataProcessor(config)
    
    # Process Excel data (or create dummy data if Excel not found)
    excel_path = "NBA_First_Basket_2025-26.xlsx"
    if not Path(excel_path).exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    players, teams = processor.process_excel_data(excel_path)
    
    # Export results
    processor.export_optimized_data(players, teams, "output_v3")
    
    log.info("🎉 Processing completed successfully!")
    log.info(f"📊 Processed {len(players)} players and {len(teams)} teams")
    
    # Show sample results
    if players:
        log.info("\n🏆 Top 5 Players by FTB Probability:")
        sorted_players = sorted(players.values(), key=lambda p: p.ftb_probability, reverse=True)[:5]
        for i, player in enumerate(sorted_players, 1):
            log.info(f"  {i}. {player.name} ({player.team}) - Grade: {player.grade} - Prob: {player.ftb_probability:.3f}")

if __name__ == "__main__":
    main()
