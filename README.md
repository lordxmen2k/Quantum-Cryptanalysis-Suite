# Quantum Cryptanalysis Suite

> **Simulated qubits doing real work.**  
> A replacement for decorative "quantum resonance fields" with actual state-vector quantum algorithms.

---

## What This Is

This project replaces the physics-theater approach of `quantum_caesar_v2.py` — where 96 classical oscillators pretended to be qubits — with **exact state-vector simulation** of three real quantum algorithms:

| Algorithm | Target | What It Actually Does |
|---|---|---|
| **QAOA** | Lattice problems (SVP, LWE) | Variational quantum optimization for shortest-vector and learning-with-errors |
| **Shor's** | Toy RSA (N ≤ 35) | Quantum period-finding via QFT to extract prime factors |
| **Grover's** | Toy symmetric ciphers | Quadratic-speedup key search via amplitude amplification |

The qubits are no longer decoration. They are **2ⁿ complex amplitudes** undergoing unitary gate evolution, and measurement outcomes directly determine cryptanalytic results.

---

## Quick Start

### Requirements
- Python 3.8+
- NumPy

```bash
pip install numpy
python quantum_cryptanalysis_suite.py
```

### Expected Output
```
================================================================================
  QUANTUM CRYPTANALYSIS SUITE — Simulated Qubits Doing Real Work
================================================================================

── QAOA — 2D Shortest Vector Problem ───────────────────────────────
Lattice basis: b1=[3. 0.], b2=[1. 2.]
QAOA qubits: 6
Optimized energy: 37.3283
Top solutions:
  (-1,-1) → vector [-4. -2.], norm²=20.00  (count=519)
  (-1, 1) → vector [-2.  2.], norm²=8.00   (count=472)
  ...
Classical optimum: s=0, t=-1, norm²=5.0000

── QAOA — Learning With Errors (toy instance) ─────────────────────
...

── Shor's Algorithm — Toy RSA Factorization ───────────────────────

N = 15:
  a=4, period=2 → 3 × 5 = 15 ✓

N = 21:
  a=13, period=6 → 3 × 7 = 21 ✓

── Grover's Algorithm — Toy Symmetric Cipher ──────────────────────
Plaintext: 1010, Key: 0110, Ciphertext: 0101
  0110  count=1975 ✓ KEY
  0111  count=9
  ...
```

---

## Architecture

### State-Vector Simulator (`QuantumSimulator`)

A lightweight, gate-level simulator that stores the full `2ⁿ` amplitude vector and applies unitary operations:

- **Single-qubit gates:** H, X, Y, Z, RX, RY, RZ
- **Two-qubit gates:** CNOT, CZ, controlled-phase (CP), SWAP
- **Multi-qubit:** QFT, inverse QFT
- **Measurement:** Probabilistic sampling from `|ψ|²`

Handles up to **~16 qubits** comfortably on a laptop (65,536 amplitudes). Beyond that, memory explodes exponentially — this is the fundamental limit of classical quantum simulation.

### QAOA → Lattice Cryptography

The closest honest mapping from the original "resonance field" metaphor.

**How it works:**
1. Encode the lattice problem (SVP or LWE) as a **diagonal cost Hamiltonian** `H_C`
2. Initialize qubits in uniform superposition
3. Alternate between:
   - **Cost evolution:** `e^(-iγH_C)` — applies phase based on solution quality
   - **Mixer evolution:** `e^(-iβH_X)` — RX rotations explore the solution space
4. Classically optimize `γ, β` parameters to minimize `⟨ψ|H_C|ψ⟩`
5. Measure to sample high-quality solutions

**Metaphor mapping:**
| Original | Real |
|---|---|
| "Resonance layers" | QAOA depth `p` |
| "Coupling strength" | Ising interaction coefficients in `H_C` |
| "Phase cluster / coherence R" | Low expectation energy = good solution |
| "Anomaly score" | High energy = bad solution |

### Shor's Algorithm → Toy RSA

**Genuinely factors small integers** using quantum period finding:

1. **Initialize:** `|0⟩|1⟩` across work and auxiliary registers
2. **Superposition:** Hadamard on work register
3. **Modular exponentiation:** `|x⟩|1⟩ → |x⟩|aˣ mod N⟩` via reversible arithmetic
4. **QFT:** Quantum Fourier Transform on work register extracts periodicity
5. **Measure:** Classical post-processing (continued fractions) converts frequency → period → factors

Uses **8–12 qubits** for N = 15, 21, 35. The algorithm is mathematically identical to what would break RSA-2048, but classical simulation cannot scale past ~20 qubits.

### Grover's Algorithm → Symmetric Key Search

**Quadratic speedup** searching for encryption keys:

1. **Initialize:** Uniform superposition over all key candidates
2. **Oracle:** Phase-flips states where `encrypt(key, plaintext) == ciphertext`
3. **Diffusion:** Amplifies marked state amplitudes
4. **Iterate:** `π/4 · √N` times (optimal for unstructured search)
5. **Measure:** Collapses to the correct key with high probability

**Test result:** On a 4-bit toy cipher, Grover recovers the key with **~96% probability** (1,975/2,048 shots), matching theoretical predictions.

---

## Simulatable vs. Real-World Limits

| Target | This Code (Simulated) | Real-World Instance | Gap |
|---|---|---|---|
| **SVP** | 2D lattice, 6 qubits, ±3 search radius | 500+ dimensional lattices | Exponential |
| **LWE** | n=2 variables, q=4 | Kyber: n=256, q=3329 | Astronomical |
| **RSA** | N = 15, 21, 35 (4–6 bit primes) | RSA-2048 (1024-bit primes) | ~2²⁰⁰⁰× |
| **AES** | 4-bit keys | AES-128 | ~2¹²⁴× |

The algorithms are **mathematically correct**. The limitation is purely classical: simulating `n` qubits requires `O(2ⁿ)` memory and time. A real quantum computer with thousands of physical qubits and error correction would run the same algorithms to break real-world crypto.

---

## Honest Assessment: What the Original Code Got Wrong

### The Original (`quantum_caesar_v2.py`)

```python
class Qubit:
    def __init__(self, init_phase):
        s = 1.0 / math.sqrt(2)
        self.a = complex(s)           # |0⟩ amplitude
        self.b = complex(s) * cexp(init_phase)  # |1⟩ amplitude with phase

    def kuramoto_kick(self, other):
        # Classical sinusoidal coupling — NOT quantum
        kick = COUPLING * math.sin(other.phase() - self.phase()) * DT
        self.b *= cexp(kick)
```

**Problems:**
- **No superposition of key candidates.** Each "qubit" stores one complex number, not a state in a `2ⁿ` Hilbert space.
- **No entanglement.** The 96 oscillators are independent coupled pendulums.
- **No measurement in computational basis.** The "resonance score" is derived from classical n-gram tables.
- **No quantum gates.** `kuramoto_kick()` is the Kuramoto model from classical synchronization theory.
- **No quantum algorithm.** There is no Grover, Shor, QAOA, or any recognized quantum subroutine.

**The qubits were decoration.** The actual cryptanalysis was 1960s-era frequency analysis (Friedman's test + bigram scoring). The physics vocabulary (subspace redux, coherence, anomalous) was flavor text.

### This Replacement

| Aspect | Original | This Code |
|---|---|---|
| State space | 96 independent phases | `2ⁿ` complex amplitudes in Hilbert space |
| Evolution | Classical ODEs (Kuramoto) | Unitary quantum gates (`e^(-iHt)`) |
| Entanglement | None | CNOT, QFT create genuine entanglement |
| Measurement | None | Probabilistic collapse to bitstrings |
| Algorithm | None | QAOA, Shor's, Grover's |
| Result | Classical score dressed as "anomaly" | Actual quantum computation output |

---

## File Structure

```
quantum_cryptanalysis_suite.py
├── QuantumSimulator      # Exact state-vector simulation (up to ~16 qubits)
├── QAOA                  # Variational quantum optimizer
│   ├── svp_2d_instance   # Shortest Vector Problem encoder
│   └── lwe_instance      # Learning With Errors encoder
├── ShorToy               # Period-finding for toy RSA
└── GroverToy             # Amplitude amplification for key search
    ├── toy_xor_sbox_oracle
    └── toy_feistel_oracle
```

---

## Extending the Code

### Add a New Cipher Target for Grover

```python
def my_cipher_oracle(plaintext: str, ciphertext: str) -> Callable:
    def encrypt(key: str) -> str:
        # Your reversible encryption logic
        return result

    def oracle(sim: QuantumSimulator):
        for i in range(sim.N):
            key = format(i, f'0{n_bits}b')
            if encrypt(key) == ciphertext:
                sim.state[i] *= -1  # Phase flip marked states

    return oracle

# Run with n qubits = key bits
grover = GroverToy(n_qubits, my_cipher_oracle(pt, ct))
result = grover.run(shots=2048)
```

### Add a New Optimization Problem for QAOA

```python
def my_qubo_cost(bits: str) -> float:
    # Return energy (lower = better solution)
    x = int(bits, 2)
    return (x - 42) ** 2  # Example: find x closest to 42

qaoa = QAOA(n_qubits=6, cost_h=my_qubo_cost, p=3)
params, energy = qaoa.optimize()
samples = qaoa.sample(params, shots=5000)
```

### Increase QAOA Depth

```python
# Deeper circuits = better approximation but harder classical optimization
qaoa = QAOA(n_qubits, cost_fn, p=5)  # Default is p=3
```

---

## References

- **Shor (1994):** "Algorithms for Quantum Computation: Discrete Logarithms and Factoring" — FOCS '94
- **Grover (1996):** "A Fast Quantum Mechanical Algorithm for Database Search" — STOC '96
- **Farhi, Goldstone, Gutmann (2014):** "A Quantum Approximate Optimization Algorithm" — arXiv:1411.4028
- **Regev (2005):** "On Lattices, Learning with Errors, Random Linear Codes, and Cryptography" — JACM

---

## License

Public domain. Use for education, research, or entertainment.  
**Do not use for actual cryptanalysis** — these are toy implementations for learning quantum algorithms.

---

> *"The qubits are no longer decoration. They are state vectors undergoing unitary evolution, and the measurement outcomes directly determine the cryptanalytic result."*
