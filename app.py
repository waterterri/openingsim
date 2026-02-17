import streamlit as st
import math
import pandas as pd
import io
from contextlib import redirect_stdout

class OpeningSim:
    def __init__(self, openingAttacks, verbosity=0):
        self.landValues = [2 * n * (n - 1) for n in range(100)]
        self.attackPenaltyRate = 12 / 1024
        self.attackLengthThresholds = [(10000, 2), (1104, 3), (0, 4)]
        self.verbosity = verbosity
        self.tick = 1
        self.layerIndex = 3
        self.land = self.landValues[self.layerIndex]
        self.troops = 512
        self.tickBonus = 0
        self.isNewAttack = False
        self.currentLandAttack = 0
        self.currentAttackTimeLeft = -1
        self.openingAttacks = openingAttacks
        self.attackIter = iter(openingAttacks)
        self.nextAttack = next(self.attackIter, None)

    def DispStats(self, *args, **kwargs):
        if self.verbosity < 1: return
        output = f"tick {self.tick: 4}  land {self.land: 5}  troops {self.troops: 5}  "
        msgs = " ".join(map(str, args))
        ctx = " ".join(f"{k} {v}" for k, v in kwargs.items())
        print(f"{output} {msgs} {ctx}".strip())

    def StartAttack(self, percentage):
        penalty = math.floor(self.troops * self.attackPenaltyRate)
        attackAmount = math.floor(self.troops * percentage / 100)
        self.currentLandAttack += attackAmount
        self.troops -= (attackAmount + penalty)
        if self.currentAttackTimeLeft == -1:
            self.isNewAttack = True
            self.currentAttackTimeLeft = 7 
        if self.verbosity >= 2:
            self.DispStats(**{"troops out": self.currentLandAttack})

    def AdvanceLayer(self, remainingTroops):
        self.layerIndex += 1
        self.land = self.landValues[self.layerIndex]
        self.currentLandAttack = remainingTroops
        duration = next((d for t, d in self.attackLengthThresholds if self.land >= t), 4)
        self.currentAttackTimeLeft = duration - 1
        if self.verbosity >= 2:
            self.DispStats(**{"troops out": self.currentLandAttack})

    def Run(self, maxTicks=500):
        if self.verbosity >= 1: self.DispStats()
        for self.tick in range(1, maxTicks + 1):
            if self.troops < 0: 
                return self.land, self.troops, False # Fixed to return 3 values

            if self.nextAttack and self.tick == self.nextAttack[0]:
                if self.verbosity >= 1: print(f"ATTACK  {self.nextAttack[1]}")
                self.StartAttack(self.nextAttack[1])
                self.nextAttack = next(self.attackIter, None)

            interest = math.floor(10000 * max((1.07 - (self.tick - 1.0001) * (0.06 / 1920)), 1.01)) / 10000
            if self.tick % 10 == 0:
                self.tickBonus += max(math.floor(self.troops * (interest - 1)), 1)
                if self.tick % 100 == 0:
                    self.tickBonus += self.land

            if self.currentAttackTimeLeft >= 0:
                if self.currentAttackTimeLeft == 0:
                    troopsNeeded = 8 * self.layerIndex
                    if self.currentLandAttack >= 1.5 * troopsNeeded:
                        self.AdvanceLayer(self.currentLandAttack - troopsNeeded)
                    elif self.isNewAttack:
                        self.troops -= (round(1.5 * troopsNeeded) - self.currentLandAttack)
                        self.AdvanceLayer(round(troopsNeeded / 2))
                    else:
                        self.troops += self.currentLandAttack
                        self.currentLandAttack = 0
                        if self.verbosity >= 1: self.DispStats(" end of attack")
                        self.currentAttackTimeLeft -= 1
                    self.isNewAttack = False
                else:
                    self.currentAttackTimeLeft -= 1

            if self.tick > 0 and self.tick % 10 == 0:
                self.troops += self.tickBonus
                self.tickBonus = 0
                if self.tick % 100 == 0:
                    if self.verbosity >= 1:
                        print("\nCYCLE")
                        self.DispStats()
                elif self.verbosity >= 2:
                    self.DispStats()
        return self.land, self.troops, (self.troops >= 0)

def FindMinAttack(knownOpening, currentTick, nextTick):
    low = 1
    high = 1024
    bestStep = None
    while low <= high:
        mid = (low + high) // 2
        testPercent = (mid / 1024) * 100
        currentAttacks = sorted(knownOpening + [[currentTick, testPercent]], key=lambda x: x)
        sim = OpeningSim(currentAttacks, verbosity=0)
        finalLand, finalTroops, success = sim.Run(maxTicks=nextTick)
        if success and sim.currentAttackTimeLeft >= 0:
            bestStep = mid
            high = mid - 1
        else:
            low = mid + 1
    return bestStep

def OptimizeChain(baseOpening, unknownTicks):
    currentOpening = [list(a) for a in baseOpening]
    results = []
    for i, thisTick in enumerate(unknownTicks):
        isLast = (i == len(unknownTicks) - 1)
        nextEventTick = (unknownTicks[i+1] if not isLast else 500) - 1
        step = FindMinAttack(currentOpening, thisTick, nextEventTick)
        if step is not None:
            percent = (step / 1024) * 100
            currentOpening.append([thisTick, percent])
            currentOpening.sort()
            results.append([thisTick, percent])
        else:
            return None, thisTick
    return sorted(currentOpening, key=lambda x: x), None

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Opening Simulator", layout="wide")

if 'base_attacks' not in st.session_state:
    st.session_state.base_attacks = [
        [64, 15.33], [81, 15.53], [91, 35.55], 
        [164, 0.10], [172, 22.17], [181, 31.35], [191, 76.27],
        [270, 0.10], [281, 43.85], [291, 85.64], 
        [371, 0.10], [381, 46.29], [391, 69.73]
    ]
if 'optimized_results' not in st.session_state:
    st.session_state.optimized_results = None

with st.sidebar:
    st.header("Controls")
    run_manual = st.button("🚀 Run Base Simulation", use_container_width=True)
    st.divider()
    st.subheader("Base Opening Attacks")
    edited_df = st.data_editor(
        pd.DataFrame(st.session_state.base_attacks, columns=["Tick", "Percent"]),
        num_rows="dynamic",
        key="base_editor",
        use_container_width=True
    )
    st.session_state.base_attacks = edited_df.values.tolist()

st.title("🎮 Opening Simulation Optimizer")
st.subheader("Chain Optimizer")
ticks_input = st.text_input("Ticks to optimize (comma separated)", "462, 471, 481, 491")
test_ticks = [int(t.strip()) for t in ticks_input.split(",") if t.strip().isdigit()]

col_opt, col_add = st.columns([1, 1])

with col_opt:
    opt_clicked = st.button("🔍 Run Optimizer", use_container_width=True)

if opt_clicked:
    with st.spinner("Calculating optimal chain..."):
        results, fail_tick = OptimizeChain(st.session_state.base_attacks, test_ticks)
        if results:
            st.session_state.optimized_results = results
            st.success("Optimization successful!")
        else:
            st.error(f"❌ Optimization FAILED. Cannot sustain the chain of attacks until tick {fail_tick}.")
            st.session_state.optimized_results = None

if st.session_state.optimized_results:
    with col_add:
        if st.button("➕ Add Attacks to Base Opening", type="primary", use_container_width=True):
            st.session_state.base_attacks = sorted(st.session_state.optimized_results)
            st.session_state.optimized_results = None
            st.rerun()

st.divider()
output_area = st.empty()

if run_manual or (opt_clicked and st.session_state.optimized_results):
    attacks_to_run = st.session_state.optimized_results if (opt_clicked and st.session_state.optimized_results) else st.session_state.base_attacks
    sim = OpeningSim(attacks_to_run, verbosity=2)
    f = io.StringIO()
    with redirect_stdout(f):
        final_land, final_troops, success = sim.Run(505)
    with output_area.container():
        st.subheader("Simulation Results")
        if success:
            st.success(f"✅ Success! | Final Land: **{final_land}** | Final Troops: **{final_troops}**")
        else:
            st.error(f"❌ Failure! | Final Land: **{final_land}** | Final Troops: **{final_troops}**")
        st.code(f.getvalue())
