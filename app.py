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
        # -1 means no attack is active right now
        
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
            self.currentAttackTimeLeft = 7 # always takes 7 ticks for the first layer of a new attack
            
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

        for self.tick in range(1, maxTicks + 1): # player spawns on tick 1, not 0
            if self.troops < 0: # failure check for optimizer
                return self.land, False

            if self.nextAttack and self.tick == self.nextAttack[0]:
                if self.verbosity >= 1: print(f"ATTACK  {self.nextAttack[1]}")
                self.StartAttack(self.nextAttack[1])
                self.nextAttack = next(self.attackIter, None)

             # interest decreases linearly from 1.07 to 1.01 over the first 1920 ticks
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

        return self.land, (self.troops >= 0)


def FindMinAttack(knownOpening, currentTick, nextTick):

    low = 1
    high = 1024
    bestStep = None

    while low <= high:
        mid = (low + high) // 2
        testPercent = (mid / 1024) * 100
        
        currentAttacks = sorted(knownOpening + [[currentTick, testPercent]], key=lambda x: x)
        sim = OpeningSim(currentAttacks, verbosity=0)
        
        # run until the next test tick
        finalLand, success = sim.Run(maxTicks=nextTick)
        
        if success and sim.currentAttackTimeLeft >= 0:
            bestStep = mid
            high = mid - 1
        else:
            low = mid + 1
            
    return bestStep


def OptimizeChain(baseOpening, unknownTicks):
   
    currentOpening = [list(a) for a in baseOpening]
    results = []

    print(f"--- STARTING CHAIN OPTIMIZATION ---")
    
    for i, thisTick in enumerate(unknownTicks):
        
        isLast = (i == len(unknownTicks) - 1)
        nextEventTick = (unknownTicks[i+1] if not isLast else int(math.ceil(max(unknownTicks) / 100)) * 100) - 1
        
        step = FindMinAttack(currentOpening, thisTick, nextEventTick)
        
        if step is not None:
            percent = (step / 1024) * 100
            currentOpening.append([thisTick, percent])
            currentOpening.sort()
            results.append({"tick": thisTick, "step": step, "percent": percent})
            print(f"Tick {thisTick:3}: Minimized to slider {step:4} / 1024 ({percent:.2f}%)")
        else:
            print(f"Tick {thisTick:3}: FAILED. Cannot sustain attack until tick {nextEventTick}.")
            return None

    return sorted(currentOpening, key=lambda x: x)


# --- [PASTE YOUR OpeningSim, FindMinAttack, AND OptimizeChain CLASSES HERE] ---

st.set_page_config(page_title="Opening Simulator", layout="wide")

# Initialize session state for the base attacks list
if 'base_attacks' not in st.session_state:
    st.session_state.base_attacks = [
        [64, 15.33], [81, 15.53], [91, 35.55], 
        [164, 0.10], [172, 22.17], [181, 31.35], [191, 76.27],
        [270, 0.10], [281, 43.85], [291, 85.64], 
        [371, 0.10], [381, 46.29], [391, 69.73]
    ]

# --- SIDEBAR ---
with st.sidebar:
    st.header("Controls")
    
    # 1. Manual Test Button at the top
    if st.button("🚀 Run Base Simulation", use_container_width=True):
        st.session_state.run_type = "manual"
    
    st.divider()
    
    st.subheader("Base Opening Attacks")
    # Data editor updates the session state
    edited_df = st.data_editor(
        pd.DataFrame(st.session_state.base_attacks, columns=["Tick", "Percent"]),
        num_rows="dynamic",
        key="data_editor"
    )
    # Sync edited data back to state
    st.session_state.base_attacks = edited_df.values.tolist()

# --- MAIN AREA ---
st.title("🎮 Opening Simulation Optimizer")

# 2. Chain Optimizer UI
st.subheader("Chain Optimizer")
ticks_input = st.text_input("Ticks to optimize (comma separated)", "462, 471, 481, 491")
test_ticks = [int(t.strip()) for t in ticks_input.split(",") if t.strip().isdigit()]

col_opt, col_add = st.columns([1, 2])

with col_opt:
    opt_clicked = st.button("🔍 Run Optimizer", use_container_width=True)

# Logic for Optimization
if opt_clicked:
    with st.spinner("Calculating optimal chain..."):
        # We need a modified OptimizeChain that returns the failure tick if it fails
        results = OptimizeChain(st.session_state.base_attacks, test_ticks)
        
        if results:
            st.session_state.optimized_results = results
            st.success("Optimization successful!")
        else:
            # Finding which tick failed (approximate based on current logic)
            st.error(f"❌ Optimization FAILED. Cannot sustain the chain of attacks.")
            st.session_state.optimized_results = None

# 3. "Add to Base" Button (only shows if optimization succeeded)
if st.session_state.get('optimized_results'):
    new_attacks = [a for a in st.session_state.optimized_results if a not in st.session_state.base_attacks]
    if new_attacks:
        with col_add:
            if st.button(f"➕ Add {len(new_attacks)} Attacks to Base Opening", type="primary"):
                st.session_state.base_attacks = sorted(st.session_state.optimized_results)
                st.rerun()

# --- OUTPUT CONSOLE ---
st.divider()
output_area = st.empty()

# Handle Simulation Execution
if st.session_state.get("run_type") == "manual" or opt_clicked:
    attacks_to_run = st.session_state.optimized_results if opt_clicked and st.session_state.get('optimized_results') else st.session_state.base_attacks
    
    sim = OpeningSim(attacks_to_run, verbosity=2)
    f = io.StringIO()
    with redirect_stdout(f):
        land, success = sim.Run(505)
    
    with output_area.container():
        st.subheader("Simulation Log")
        status_color = "green" if success else "red"
        st.markdown(f"**Final Land:** `{land}` | **Success:** :{status_color}[{success}]")
        st.code(f.getvalue())
    
    # Reset run type
    st.session_state.run_type = None
