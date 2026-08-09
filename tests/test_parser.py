import unittest
from monitor import BridgeParser

class ParserTests(unittest.TestCase):
    def test_v107_json(self):
        payload = {
            "totalBlocks": 2,
            "totalKasBlocks": 1,
            "totalShares": 99,
            "activeWorkers": 2,
            "blocks": [{"worker":"A","wallet":"zkas:abc","timestamp":"1","hash":"zhash","nonce":"3","bluescore":"4"}],
            "kasBlocks": [{"worker":"A","zkasWallet":"zkas:abc","kasWallet":"kaspa:def","timestamp":"2","hash":"khash","nonce":"5","daaScore":"6","rewardSompi":231246515}]
        }
        s = BridgeParser.parse_json(payload)
        self.assertEqual(s.zkas_total, 2)
        self.assertEqual(s.kas_total, 1)
        self.assertEqual(s.active_workers, 2)
        self.assertEqual(s.total_shares, 99)
        self.assertEqual(s.zkas_blocks[0].hash, "zhash")
        self.assertEqual(s.kas_blocks[0].payout_wallet, "kaspa:def")
        self.assertAlmostEqual(s.kas_blocks[0].reward_kas(), 2.31246515)

    def test_future_aliases(self):
        payload = {
            "totalZkasBlocks": 3,
            "kasBlocksTotal": 4,
            "recentZkasBlocks": [{"blockHash":"z2","workerName":"B"}],
            "recentKasBlocks": [{"block_hash":"k2","worker_name":"B","payout_wallet":"kaspa:x"}],
        }
        s = BridgeParser.parse_json(payload)
        self.assertEqual((s.zkas_total, s.kas_total), (3, 4))
        self.assertEqual(s.zkas_blocks[0].hash, "z2")
        self.assertEqual(s.kas_blocks[0].hash, "k2")

    def test_metrics(self):
        metrics = r"""
ks_mined_blocks_gauge{worker="W",wallet="zkas:a",hash="zh"} 1
ks_blocks_mined{worker="W"} 1
ks_merged_kas_blocks_gauge{worker="W",zkas_wallet="zkas:a",kas_wallet="kaspa:b",hash="kh",reward_sompi="231246515"} 1
ks_merged_kas_blocks_accepted_total{worker="W"} 1
ks_valid_share_counter{worker="W"} 42
"""
        s = BridgeParser.parse_metrics(metrics)
        self.assertEqual((s.zkas_total, s.kas_total, s.total_shares), (1, 1, 42))

if __name__ == "__main__":
    unittest.main()
