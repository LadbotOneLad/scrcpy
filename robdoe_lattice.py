import hashlib
import math
import random
import subprocess

class RobdoeLattice:
    ARC_TOTAL = 1296000
    MACRO_CYCLE_YRS = 260000
    OPERATIONAL_WINDOW_YRS = 80
    WOBBLE_RATIO = OPERATIONAL_WINDOW_YRS / MACRO_CYCLE_YRS  # The precessional compression factor

    def __init__(self, states):
        self.states = states
        self.transition_matrix = {s: {target: 1.0 / len(states) for target in states} for s in states}
        self.phases = {s: random.uniform(0, 2 * math.pi) for s in states}
        self.merkle_history = []
        self.current_state = states[0]
        self.record_state(self.current_state)

    def get_git_leaf(self, tag_name):
        try:
            res = subprocess.run(
                ["git", "rev-parse", f"tags/{tag_name}^{{commit}}"],
                capture_output=True, text=True, check=True
            )
            return res.stdout.strip()
        except Exception:
            return hashlib.sha256(tag_name.encode()).hexdigest()[:12]

    def record_state(self, data):
        git_leaf = self.get_git_leaf(data)
        current_phase = self.phases[self.current_state]
        self.merkle_history.append((data, git_leaf, current_phase))

    def get_theta_merkle_root(self):
        if not self.merkle_history:
            return "GENESIS:e14f9a8d"
        
        leaves = []
        for state, git_leaf, phase in self.merkle_history:
            # Scale arcseconds through the macro-to-micro wobble ratio
            arc_val = ((phase / (2 * math.pi)) * self.ARC_TOTAL) * self.WOBBLE_RATIO
            leaf_str = f"wobble_arcs:{arc_val:.6f}|state:{state}|git:{git_leaf}"
            leaves.append(hashlib.sha256(leaf_str.encode()).hexdigest())
            
        current_level = leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
                combined = (left + right).encode()
                next_level.append(hashlib.sha256(combined).hexdigest())
            current_level = next_level
            
        return current_level[0]

    def kuramoto_step(self, K=0.5, dt=0.1):
        new_phases = {}
        n = len(self.states)
        for s_i in self.states:
            theta_i = self.phases[s_i]
            coupling_sum = sum(math.sin(self.phases[s_j] - theta_i) for s_j in self.states if s_i != s_j)
            d_theta = 1.0 + (K / n) * coupling_sum
            new_phases[s_i] = (theta_i + d_theta * dt) % (2 * math.pi)
        self.phases = new_phases

    def markov_transition(self):
        probs = self.transition_matrix[self.current_state]
        next_state = random.choices(list(probs.keys()), weights=list(probs.values()))[0]
        self.current_state = next_state
        self.record_state(next_state)
        return next_state

if __name__ == "__main__":
    flow = ["robdoe-root", "robdoe-operator", "robdoe-checkpoint", "robdoe-sentinel"]
    lattice = RobdoeLattice(flow)
    for _ in range(3):
        lattice.kuramoto_step(K=1.2, dt=0.05)
        nxt = lattice.markov_transition()
        state, leaf, phase = lattice.merkle_history[-1]
        wobble_arcs = ((phase / (2 * math.pi)) * lattice.ARC_TOTAL) * lattice.WOBBLE_RATIO
        root_hash = lattice.get_theta_merkle_root()
        print(f"State: {state} | Wobble Arcs: {wobble_arcs:.4f}'' | Git Leaf: {leaf[:8]} | Theta Merkle Root: {root_hash[:16]}")
