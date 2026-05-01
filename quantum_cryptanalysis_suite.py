"""
Quantum Cryptanalysis Suite — Simulated Qubits Doing Real Work
===============================================================

Replaces the decorative "resonance field" from quantum_caesar_v2.py with
actual quantum algorithms running on exact state-vector simulation.

Targets:
  • QAOA      → Lattice problems (SVP, LWE) — optimization via quantum annealing
  • Shor's    → Toy RSA factorization — period finding via QFT
  • Grover's  → Toy symmetric cipher key search — amplitude amplification

Architecture mapping from original code:
  Original "resonance layers" (p)  →  QAOA depth / Grover iterations
  Original "coupling"              →  Ising ZZ interactions / diffusion operator
  Original "noise/nudge"           →  Mixer X rotations (beta)
  Original "coherence R"           →  Expectation ⟨ψ|H|ψ⟩ or measurement probability
  Original "anomaly score"         →  Classical optimization or search failure

Simulatable limits (laptop, ~16 qubits):
  • QAOA:   6–10 qubits  →  2D SVP, tiny LWE
  • Shor:   8–12 qubits  →  N = 15, 21, 35
  • Grover: 4–6 qubits   →  4–6 bit keys

Real-world instances require physical quantum hardware (thousands of qubits).
"""

import numpy as np
import math
import random
from typing import List, Tuple, Dict, Callable, Optional


# ═══════════════════════════════════════════════════════════════════════
# PART 1: Exact State-Vector Quantum Simulator
# ═══════════════════════════════════════════════════════════════════════

class QuantumSimulator:
    """
    Lightweight state-vector simulator.
    Handles up to ~16 qubits comfortably on a laptop (2^16 = 65,536 amplitudes).
    """
    def __init__(self, n_qubits: int):
        self.n = n_qubits
        self.N = 1 << n_qubits
        self.state = np.zeros(self.N, dtype=complex)
        self.state[0] = 1.0

    def reset(self):
        self.state.fill(0)
        self.state[0] = 1.0

    def h(self, q: int):
        stride = 1 << q
        inv_sqrt2 = 1.0 / math.sqrt(2)
        for base in range(0, self.N, stride << 1):
            for j in range(base, base + stride):
                a, b = self.state[j], self.state[j + stride]
                self.state[j] = (a + b) * inv_sqrt2
                self.state[j + stride] = (a - b) * inv_sqrt2

    def h_all(self):
        for i in range(self.n):
            self.h(i)

    def x(self, q: int):
        stride = 1 << q
        for base in range(0, self.N, stride << 1):
            for j in range(base, base + stride):
                self.state[j], self.state[j + stride] =                     self.state[j + stride], self.state[j]

    def z(self, q: int):
        stride = 1 << q
        for base in range(0, self.N, stride << 1):
            for j in range(base, base + stride):
                self.state[j + stride] *= -1

    def rx(self, theta: float, q: int):
        c, s = math.cos(theta / 2), -1j * math.sin(theta / 2)
        stride = 1 << q
        for base in range(0, self.N, stride << 1):
            for j in range(base, base + stride):
                a, b = self.state[j], self.state[j + stride]
                self.state[j] = c * a + s * b
                self.state[j + stride] = s * a + c * b

    def cnot(self, c: int, t: int):
        if c == t:
            return
        old = self.state.copy()
        mask_c = 1 << c
        mask_t = 1 << t
        for i in range(self.N):
            if i & mask_c:
                self.state[i] = old[i ^ mask_t]

    def cp(self, theta: float, c: int, t: int):
        old = self.state.copy()
        phase = complex(math.cos(theta), math.sin(theta))
        mask_c = 1 << c
        mask_t = 1 << t
        for i in range(self.N):
            if (i & mask_c) and (i & mask_t):
                self.state[i] = old[i] * phase

    def swap(self, q1: int, q2: int):
        old = self.state.copy()
        m1 = 1 << q1
        m2 = 1 << q2
        for i in range(self.N):
            b1 = (i & m1) >> q1
            b2 = (i & m2) >> q2
            if b1 != b2:
                self.state[i] = old[i ^ m1 ^ m2]

    def qft(self, qubits: Optional[List[int]] = None):
        if qubits is None:
            qubits = list(range(self.n))
        n = len(qubits)
        for i in range(n):
            self.h(qubits[i])
            for j in range(i + 1, n):
                angle = math.pi / (2 ** (j - i))
                self.cp(angle, qubits[j], qubits[i])
        for i in range(n // 2):
            self.swap(qubits[i], qubits[n - 1 - i])

    def measure(self, shots: int = 1024) -> Dict[str, int]:
        probs = np.abs(self.state) ** 2
        probs = probs / probs.sum()
        outcomes = np.random.choice(self.N, size=shots, p=probs)
        counts = {}
        for o in outcomes:
            b = format(o, f'0{self.n}b')
            counts[b] = counts.get(b, 0) + 1
        return counts

    def measure_most_likely(self) -> str:
        return format(int(np.argmax(np.abs(self.state) ** 2)), f'0{self.n}b')


# ═══════════════════════════════════════════════════════════════════════
# PART 2: QAOA — Quantum Approximate Optimization Algorithm
# ═══════════════════════════════════════════════════════════════════════

class QAOA:
    """
    QAOA for combinatorial optimization.

    Maps the original "resonance field" metaphor:
      - Layers (p)        →  QAOA depth (repetitions of cost + mixer)
      - Coupling          →  Ising ZZ interactions (gamma parameters)
      - Noise/Nudge       →  Mixer X rotations (beta parameters)
      - Coherence R       →  Expectation value ⟨ψ|H_C|ψ⟩ (lower = better)
      - Anomaly score     →  Classical optimizer minimizing energy
    """

    def __init__(self, n_qubits: int, cost_h: Callable[[str], float], p: int = 3):
        self.n = n_qubits
        self.cost_h = cost_h
        self.p = p
        self.sim = QuantumSimulator(n_qubits)
        self._cost_array = np.array([
            cost_h(format(i, f'0{n_qubits}b'))
            for i in range(1 << n_qubits)
        ], dtype=float)

    def _apply_cost(self, gamma: float):
        phases = np.exp(-1j * gamma * self._cost_array)
        self.sim.state *= phases

    def _circuit(self, params: np.ndarray):
        self.sim.reset()
        self.sim.h_all()
        gammas = params[:self.p]
        betas = params[self.p:]
        for layer in range(self.p):
            self._apply_cost(gammas[layer])
            for q in range(self.n):
                self.sim.rx(2 * betas[layer], q)

    def energy(self, params: np.ndarray) -> float:
        self._circuit(params)
        probs = np.abs(self.sim.state) ** 2
        return float(np.sum(self._cost_array * probs))

    def optimize(self, max_iter: int = 300) -> Tuple[np.ndarray, float]:
        best_energy = float('inf')
        best_params = None
        for restart in range(20):
            params = np.random.uniform(-np.pi, np.pi, 2 * self.p)
            curr_e = self.energy(params)
            for _ in range(max_iter):
                idx = random.randrange(2 * self.p)
                delta = random.uniform(-0.5, 0.5)
                new_params = params.copy()
                new_params[idx] += delta
                new_params = np.clip(new_params, -2 * np.pi, 2 * np.pi)
                new_e = self.energy(new_params)
                if new_e < curr_e:
                    params = new_params
                    curr_e = new_e
            if curr_e < best_energy:
                best_energy = curr_e
                best_params = params
        return best_params, best_energy

    def sample(self, params: np.ndarray, shots: int = 3000) -> Dict[str, int]:
        self._circuit(params)
        return self.sim.measure(shots)


# --- Lattice Problem Encoders ---

def svp_2d_instance(basis: np.ndarray, radius: int = 3):
    """2D Shortest Vector Problem → QAOA cost function."""
    b1, b2 = basis[0], basis[1]
    n_bits = 3
    offset = radius
    n_qubits = 2 * n_bits

    def decode(bits: str) -> Tuple[int, int]:
        x = int(bits[:n_bits], 2) - offset
        y = int(bits[n_bits:], 2) - offset
        return x, y

    def cost(bits: str) -> float:
        x, y = decode(bits)
        if x == 0 and y == 0:
            return 1000.0
        v = x * b1 + y * b2
        return float(np.dot(v, v))

    return n_qubits, cost, decode


def lwe_instance(A: np.ndarray, b: np.ndarray, q: int):
    """Small LWE instance → QAOA cost function."""
    m, n = A.shape
    bits_per = int(np.ceil(np.log2(q)))
    n_qubits = n * bits_per

    def decode(bits: str) -> np.ndarray:
        s = np.zeros(n, dtype=int)
        for i in range(n):
            val = int(bits[i * bits_per:(i + 1) * bits_per], 2)
            s[i] = min(val, q - 1)
        return s

    def cost(bits: str) -> float:
        s = decode(bits)
        total = 0.0
        for j in range(m):
            diff = int((np.dot(A[j], s) - b[j]) % q)
            dist = min(diff, q - diff)
            total += dist ** 2
        for i in range(n):
            val = int(bits[i * bits_per:(i + 1) * bits_per], 2)
            if val >= q:
                total += 100.0
        return total

    return n_qubits, cost, decode


# ═══════════════════════════════════════════════════════════════════════
# PART 3: Shor's Algorithm — Toy RSA Factorization
# ═══════════════════════════════════════════════════════════════════════

class ShorToy:
    """
    Simulated Shor's algorithm using exact state-vector evolution.
    For N = 15, 21, 35 (toy RSA instances).

    Architecture mapping:
      - "Resonance"       →  QFT peak extraction
      - "Coherence R"     →  Probability concentration at period multiples
      - "Anomaly"         →  Failed factorization (wrong period)
    """

    def __init__(self, N: int):
        self.N = N
        self.n_work = max(4, int(np.ceil(np.log2(2 * N))))
        self.n_aux = max(4, int(np.ceil(np.log2(N))))
        self.total = self.n_work + self.n_aux

    def run(self, a: Optional[int] = None, shots: int = 4096) -> Tuple[int, int, Optional[int]]:
        if a is None:
            while True:
                a = random.randint(2, self.N - 1)
                if math.gcd(a, self.N) == 1:
                    break

        if math.gcd(a, self.N) != 1:
            p = math.gcd(a, self.N)
            return p, self.N // p, None

        sim = QuantumSimulator(self.total)

        for q in range(self.n_work):
            sim.h(q)
        sim.x(self.n_work)

        for i in range(self.n_work):
            ap = pow(a, 2 ** i, self.N)
            self._c_mult(sim, i, ap)

        sim.qft(list(range(self.n_work)))

        # Marginal measurement of work register
        probs = np.abs(sim.state) ** 2
        work_probs = np.zeros(1 << self.n_work)
        for i in range(sim.N):
            work = i >> self.n_aux
            work_probs[work] += probs[i]
        work_probs /= work_probs.sum()

        outcomes = np.random.choice(1 << self.n_work, size=shots, p=work_probs)
        counts = {}
        for o in outcomes:
            b = format(o, f'0{self.n_work}b')
            counts[b] = counts.get(b, 0) + 1

        best_period = None
        best_conf = 0
        denom_limit = 2 * self.N

        for bitstring, count in counts.items():
            measured = int(bitstring, 2)
            if measured == 0:
                continue
            frac = measured / (1 << self.n_work)
            for denom in range(1, denom_limit):
                num = round(frac * denom)
                if abs(frac - num / denom) < 0.5 / (1 << self.n_work):
                    if pow(a, denom, self.N) == 1:
                        if count > best_conf:
                            best_period = denom
                            best_conf = count

        if best_period is None:
            return 0, 0, None

        if best_period % 2 == 0:
            p = math.gcd(pow(a, best_period // 2, self.N) - 1, self.N)
            q = self.N // p
            if p > 1 and p < self.N:
                return p, q, best_period

        return 0, 0, best_period

    def _c_mult(self, sim: QuantumSimulator, ctrl: int, a: int):
        old = sim.state.copy()
        mask_ctrl = 1 << ctrl
        mask_aux = (1 << self.n_aux) - 1
        sim.state.fill(0)
        for i in range(sim.N):
            if (i & mask_ctrl) == 0:
                sim.state[i] += old[i]
            else:
                work = i >> self.n_aux
                aux = i & mask_aux
                if aux < self.N:
                    new_aux = (aux * a) % self.N
                    new_i = (work << self.n_aux) | new_aux
                    sim.state[new_i] += old[i]
                else:
                    sim.state[i] += old[i]
        norm = np.linalg.norm(sim.state)
        if norm > 1e-15:
            sim.state /= norm


# ═══════════════════════════════════════════════════════════════════════
# PART 4: Grover's Algorithm — Toy Symmetric Cipher Key Search
# ═══════════════════════════════════════════════════════════════════════

class GroverToy:
    """
    Grover's search for toy symmetric ciphers.

    Architecture mapping:
      - Resonance layers  →  Grover iterations (oracle + diffusion)
      - Coupling          →  Diffusion operator
      - Coherence         →  Probability concentration at marked state
    """

    def __init__(self, n_qubits: int, oracle: Callable[[QuantumSimulator], None]):
        self.n = n_qubits
        self.N = 1 << n_qubits
        self.oracle = oracle

    def _diffusion(self, sim: QuantumSimulator):
        sim.h_all()
        for q in range(self.n):
            sim.x(q)
        # Multi-controlled Z (phase flip on |11...1⟩)
        if self.n <= 3:
            if self.n == 1:
                sim.z(0)
            elif self.n == 2:
                # CZ via CNOT + H
                sim.h(1)
                sim.cnot(0, 1)
                sim.h(1)
            elif self.n == 3:
                sim.h(2)
                sim.cnot(0, 2)
                sim.cnot(1, 2)
                sim.h(2)
        else:
            # For n >= 4: direct phase flip on all-ones state
            old = sim.state.copy()
            for i in range(sim.N):
                if i == sim.N - 1:
                    sim.state[i] = -old[i]
        for q in range(self.n):
            sim.x(q)
        sim.h_all()

    def run(self, iterations: Optional[int] = None, shots: int = 1024) -> Dict[str, int]:
        if iterations is None:
            iterations = int(round(math.pi / 4 * math.sqrt(self.N)))

        sim = QuantumSimulator(self.n)
        sim.h_all()

        for _ in range(iterations):
            self.oracle(sim)
            self._diffusion(sim)

        return sim.measure(shots)


def toy_xor_sbox_oracle(plaintext: str, ciphertext: str, sbox: List[int]) -> Callable:
    """Toy cipher: XOR key, then S-box on 4-bit chunks."""
    n = len(plaintext)

    def encrypt(key: str) -> str:
        xored = ''.join(str(int(p) ^ int(k)) for p, k in zip(plaintext, key))
        out = []
        for i in range(0, n, 4):
            chunk = xored[i:i + 4]
            if len(chunk) == 4:
                val = int(chunk, 2)
                out.append(format(sbox[val % len(sbox)], '04b'))
            else:
                out.append(chunk)
        return ''.join(out)

    def oracle(sim: QuantumSimulator):
        for i in range(sim.N):
            key = format(i, f'0{n}b')
            if encrypt(key) == ciphertext:
                sim.state[i] *= -1

    return oracle


def toy_feistel_oracle(plaintext: str, ciphertext: str, rounds: int = 2) -> Callable:
    """Toy Feistel cipher."""
    n = len(plaintext)
    half = n // 2

    def feistel_round(left: str, right: str, key: str, rn: int) -> Tuple[str, str]:
        round_key = ''.join(str(int(k) ^ (rn & 1)) for k in key[:half])
        f_out = ''.join(str(int(r) ^ int(k)) for r, k in zip(right, round_key))
        f_out = f_out[1:] + f_out[0]
        new_right = ''.join(str(int(l) ^ int(f)) for l, f in zip(left, f_out))
        return right, new_right

    def encrypt(key: str) -> str:
        left, right = plaintext[:half], plaintext[half:]
        for r in range(rounds):
            left, right = feistel_round(left, right, key, r)
        return left + right

    def oracle(sim: QuantumSimulator):
        for i in range(sim.N):
            key = format(i, f'0{n}b')
            if encrypt(key) == ciphertext:
                sim.state[i] *= -1

    return oracle


# ═══════════════════════════════════════════════════════════════════════
# PART 5: Demo / Test Suite
# ═══════════════════════════════════════════════════════════════════════

def demo():
    print("\n" + "=" * 72)
    print("  QUANTUM CRYPTANALYSIS SUITE — Simulated Qubits Doing Real Work")
    print("=" * 72)

    # ── QAOA: Shortest Vector Problem ─────────────────────────────────
    print("\n── QAOA — 2D Shortest Vector Problem ───────────────────────────────")
    basis = np.array([[3.0, 0.0], [1.0, 2.0]])
    n_q, cost_fn, decode_fn = svp_2d_instance(basis, radius=3)
    print(f"Lattice basis: b1={basis[0]}, b2={basis[1]}")
    print(f"QAOA qubits: {n_q}")

    qaoa = QAOA(n_q, cost_fn, p=3)
    best_params, best_e = qaoa.optimize(max_iter=300)
    print(f"Optimized energy: {best_e:.4f}")

    samples = qaoa.sample(best_params, shots=5000)
    top = sorted(samples.items(), key=lambda x: -x[1])[:5]
    print("Top solutions:")
    for bits, count in top:
        x, y = decode_fn(bits)
        v = x * basis[0] + y * basis[1]
        print(f"  ({x:2d},{y:2d}) → vector {v.round(2)}, norm²={np.dot(v,v):.2f}  (count={count})")

    # Classical verification
    best_cv = None
    best_cn = float('inf')
    for x in range(-3, 4):
        for y in range(-3, 4):
            if x == 0 and y == 0:
                continue
            v = x * basis[0] + y * basis[1]
            n2 = np.dot(v, v)
            if n2 < best_cn:
                best_cn = n2
                best_cv = (x, y)
    print(f"Classical optimum: s={best_cv[0]}, t={best_cv[1]}, norm²={best_cn:.4f}")

    # ── QAOA: LWE ─────────────────────────────────────────────────────
    print("\n── QAOA — Learning With Errors (toy instance) ─────────────────────")
    q = 4
    n = 2
    m = 3
    secret = np.array([1, 2])
    np.random.seed(42)
    A = np.random.randint(0, q, size=(m, n))
    e = np.array([0, 1, 0])
    b = (A @ secret + e) % q
    print(f"LWE: n={n}, m={m}, q={q}, secret={secret}")
    print(f"A =\n{A}")
    print(f"b = {b}")

    n_q, cost_fn, decode_fn = lwe_instance(A, b, q)
    qaoa2 = QAOA(n_q, cost_fn, p=4)
    bp, be = qaoa2.optimize(max_iter=400)
    print(f"Optimized energy: {be:.4f}")

    samples2 = qaoa2.sample(bp, shots=5000)
    top2 = sorted(samples2.items(), key=lambda x: -x[1])[:5]
    for bits, count in top2:
        s = decode_fn(bits)
        pred = (A @ s) % q
        err = sum(min(int((pred[i] - b[i]) % q), q - int((pred[i] - b[i]) % q)) for i in range(m))
        print(f"  s={s} → A·s mod q = {pred} → error={err}  (count={count})")

    # ── Shor's Algorithm ──────────────────────────────────────────────
    print("\n── Shor's Algorithm — Toy RSA Factorization ───────────────────────")
    for N in [15, 21, 35]:
        print(f"\nN = {N}:")
        shor = ShorToy(N)
        found = False
        for trial in range(8):
            a = random.randint(2, N - 1)
            if math.gcd(a, N) != 1:
                p = math.gcd(a, N)
                print(f"  a={a} shares factor → {p} × {N // p} = {N} ✓")
                found = True
                break
            p, qv, period = shor.run(a=a, shots=4096)
            if p > 1 and p < N:
                print(f"  a={a}, period={period} → {p} × {qv} = {N} ✓")
                found = True
                break
        if not found:
            print(f"  Failed after 8 trials")

    # ── Grover's Algorithm ────────────────────────────────────────────
    print("\n── Grover's Algorithm — Toy Symmetric Cipher ──────────────────────")
    plaintext = "1010"
    key = "0110"
    SBOX = [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7]
    xored = ''.join(str(int(p) ^ int(k)) for p, k in zip(plaintext, key))
    ciphertext = format(SBOX[int(xored, 2)], '04b')
    print(f"Plaintext: {plaintext}, Key: {key}, Ciphertext: {ciphertext}")

    oracle = toy_xor_sbox_oracle(plaintext, ciphertext, SBOX)
    grover = GroverToy(4, oracle)
    result = grover.run(shots=2048)
    for bits, count in sorted(result.items(), key=lambda x: -x[1])[:5]:
        marker = " ✓ KEY" if bits == key else ""
        print(f"  {bits}  count={count}{marker}")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    demo()
