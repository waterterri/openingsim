import streamlit as st
import math
import pandas as pd

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

st.set_page_config(page_title="Game Simulation Optimizer", layout="wide")

st.title("🎮 Opening Simulation Optimizer")

# Sidebar: Base Configuration
st.sidebar.header("Base Attacks")
base_data = pd.DataFrame([
    [64, 15.33], [81, 15.53], [91, 35.55], 
    [164, 0.10], [172, 22.17], [181, 31.35], [191, 76.27]
], columns=["Tick", "Percent"])

edited_base = st.sidebar.data_editor(base_data, num_rows="dynamic")

# Main UI: Chain Optimization
col1, col2 = st.columns(2)

with col1:
    st.subheader("Chain Optimizer")
    ticks_input = st.text_input("Ticks to optimize (comma separated)", "462, 471, 481, 491")
    
    if st.button("Run Optimizer"):
        test_ticks = [int(t.strip()) for t in ticks_input.split(",")]
        base_list = edited_base.values.tolist()
        
        with st.spinner("Optimizing..."):
            optimized = OptimizeChain(base_list, test_ticks)
            
        if optimized:
            st.success("Optimization Complete!")
            st.dataframe(pd.DataFrame(optimized, columns=["Tick", "Percent"]))
            
            # Verification Run
            st.subheader("Simulation Log")
            sim = OpeningSim(optimized, verbosity=1)
            # Capture stdout to show in web app
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                sim.Run(505)
            st.code(f.getvalue())

with col2:
    st.subheader("Manual Test")
    single_tick = st.number_input("Test Tick", value=462)
    single_percent = st.slider("Test Percentage", 0.0, 100.0, 15.0)
    
    if st.button("Test Single Run"):
        manual_attacks = edited_base.values.tolist() + [[single_tick, single_percent]]
        sim = OpeningSim(manual_attacks, verbosity=2)
        f = io.StringIO()
        with redirect_stdout(f):
            land, success = sim.Run(505)
        st.write(f"**Success:** {success} | **Final Land:** {land}")
        st.code(f.getvalue())
