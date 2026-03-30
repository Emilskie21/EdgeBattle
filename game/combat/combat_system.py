from game.combat.player_stats import PlayerStats


class CombatSystem:
    def on_matched_shown_arrow(self, stats: PlayerStats) -> None:
        """Player moved head the same way as the on-screen arrow — takes a hit."""
        stats.damage(1)
