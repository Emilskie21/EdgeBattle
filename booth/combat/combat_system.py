from combat.player_stats import PlayerStats


class CombatSystem:
    def on_player_sequence_success(self, stats: PlayerStats) -> None:
        stats.add_score(250)

    def on_player_sequence_fail(self, stats: PlayerStats) -> None:
        stats.damage(1)

    def on_enemy_hit(self, stats: PlayerStats) -> None:
        stats.damage(1)

    def on_enemy_dodged(self, stats: PlayerStats) -> None:
        stats.add_score(125)
