import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pg_remnants.estimates import Estimate, RevealModel, MINUTE
from pg_remnants.intel import reveal_detail
from pg_remnants.model import Snapshot
from pg_remnants.storage import Store
from tests.helpers import NOW, event


class EstimateTests(unittest.TestCase):
    def setUp(self):
        s = Snapshot.from_event(event(), 2, NOW)
        self.before = replace(s, carriers=(replace(s.carriers[0], spawn_ms=NOW-23*MINUTE, departure_ms=None),))
        self.after = replace(self.before, observed_ms=NOW+3*MINUTE,
                             carriers=(replace(self.before.carriers[0], category='tank'),))

    def test_clean_transition_learns_age_and_separates_cohorts(self):
        model = RevealModel()
        model.observe(self.before); model.observe(self.after)
        estimates = model.estimates(2)
        self.assertEqual(estimates[('regular','category')], Estimate(1, int(24.5*MINUTE),23*MINUTE,26*MINUTE))
        self.assertNotIn(('boss','category'), estimates)
        self.assertNotIn(('regular','planet'), estimates)
        self.assertEqual(model.estimates(3), {})
        self.assertEqual(model.estimates(2,NOW+4*MINUTE), {})

    def test_attack_stale_gap_and_already_known_are_excluded(self):
        for scenario in ('hp100','hp0','departure','stale_before','stale_after','outage','already_known','missing'):
            with self.subTest(scenario=scenario):
                a,b = self.before,self.after
                if scenario.startswith('hp'):
                    b = replace(b,carriers=(replace(b.carriers[0],hp=int(scenario[2:])),))
                if scenario=='departure': b=replace(b,carriers=(replace(b.carriers[0],departure_ms=NOW+MINUTE),))
                if scenario=='stale_before': a=replace(a,fresh_session=False)
                if scenario=='stale_after': b=replace(b,fresh_session=False)
                if scenario=='outage': b=replace(b,observed_ms=NOW+10*MINUTE)
                if scenario=='already_known': a=replace(a,carriers=b.carriers)
                if scenario=='missing': a=replace(a,carriers=())
                model=RevealModel(); model.observe(a); model.observe(b)
                self.assertEqual(model.estimates(2),{})

    def test_previous_combat_and_repeated_disclosures_do_not_train(self):
        for first in (replace(self.before.carriers[0],hp=100), self.after.carriers[0]):
            model=RevealModel()
            model.observe(replace(self.before,observed_ms=NOW-MINUTE,carriers=(first,)))
            model.observe(self.before); model.observe(self.after)
            self.assertEqual(model.estimates(2),{})

    def test_fresh_graph_counts_and_reload_preserves_estimates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.sqlite3'
            store=Store(path)
            for s in (self.before,self.after):
                store.record(replace(s,fresh_session=False,fresh_graph=True),30)
            expected=store.reveal_estimates(self.after)
            self.assertEqual(expected[('regular','category')].count,1)
            self.assertEqual(store.intel_history(self.after)[self.before.carriers[0].key]['category']['last_unknown'],NOW)
            store.close(); store=Store(path)
            self.assertEqual(store.reveal_estimates(self.after),expected)
            store.close()

    def test_estimate_never_overrides_known_or_claims_reveal(self):
        c=self.before.carriers[0]; e=Estimate(1,25*MINUTE,23*MINUTE,26*MINUTE)
        self.assertIn('Geschätzt ~2 min',reveal_detail(c,'category',NOW,estimate=e))
        self.assertIn('verstrichen',reveal_detail(c,'category',NOW+4*MINUTE,estimate=e))
        self.assertNotIn('~',reveal_detail(c,'category',NOW,estimate=e,stale=True))
        self.assertEqual(reveal_detail(self.after.carriers[0],'category',NOW,estimate=e),'Bereits bekannt')
        self.assertIn('noch keine Messung',reveal_detail(c,'planet',NOW))


if __name__ == '__main__':
    unittest.main()
