import streamlit as st
import math
import pandas as pd
import io
from contextlib import redirect_stdout

# --- CORE LOGIC ---
class OpeningSim:
    def __init__(self, openingAttacks, verbosity=0):
        self.landValues = [2 * n * (n - 1) for n in range(100)]
        self.attackPenaltyRate = 12 / 1024
        self.attackLengthThresholds = [(10512, 2), (1104, 3), (0, 4)]
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
                return self.land, self.troops, False 

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
        currentAttacks = sorted(knownOpening + [[currentTick, testPercent]], key=lambda x: x[0])
        sim = OpeningSim(currentAttacks, verbosity=0)
        finalLand, finalTroops, success = sim.Run(maxTicks=nextTick)
        if success and sim.currentAttackTimeLeft >= 0:
            bestStep = mid
            high = mid - 1
        else:
            low = mid + 1
    return bestStep

def OptimizeChain(baseOpening, unknownTicks):
    currentOpening = [list(a) for a in baseOpening if a[0] is not None]
    for i, thisTick in enumerate(unknownTicks):
        isLast = (i == len(unknownTicks) - 1)
        nextEventTick = (unknownTicks[i+1] if not isLast else int(math.ceil(max(unknownTicks) / 100)) * 100) - 1
        step = FindMinAttack(currentOpening, thisTick, nextEventTick)
        if step is not None:
            percent = (step / 1024) * 100
            currentOpening.append([thisTick, percent])
            currentOpening.sort()
        else:
            return None, thisTick
    return sorted(currentOpening, key=lambda x: x[0]), None

# --- UI SETUP ---
st.set_page_config(page_title="Opening Simulator", layout="wide")

# Initialize session state
if 'base_attacks' not in st.session_state:
    st.session_state.base_attacks = []
if 'optimized_results' not in st.session_state:
    st.session_state.optimized_results = None
if 'sim_output' not in st.session_state:
    st.session_state.sim_output = None

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Controls")
    num_cycles = st.number_input("Cycles to simulate", min_value=1, max_value=20, value=5)
    sim_ticks = (num_cycles * 100) + 5
    # Multiplayer mode toggle
    multiplayer_mode = st.checkbox("Enable Multiplayer Mode", value=False, key="multiplayer_mode")
    run_manual = st.button("🚀 Run Base Simulation", use_container_width=True)
    if st.button("🗑️ Clear All Attacks", use_container_width=True):
        st.session_state.base_attacks = []
        st.session_state.optimized_results = None
        st.session_state.sim_output = None
        st.rerun()

    st.divider()

    # Attack editor
    with st.form("attack_editor_form"):
        st.subheader("Base Opening Attacks")
        current_df = pd.DataFrame(
            [r for r in st.session_state.base_attacks if r is not None and not all(x is None for x in r)],
            columns=["Tick", "Percent"]
        )
        edited_df = st.data_editor(current_df, num_rows="dynamic", key="editor_inside_form", use_container_width=True)
        if st.form_submit_button("💾 Apply Changes", use_container_width=True):
            raw_edits = edited_df.values.tolist()
            st.session_state.base_attacks = [r for r in raw_edits if not all(x is None for x in r)]
            st.rerun()

# --- Main Content ---
st.title("Water's Opening Simulator")
st.subheader("Chain Optimizer")

# Calculate next cycle window based on existing attacks
def get_next_cycle_window():
    current_max_tick = -1
    if 'base_attacks' in st.session_state:
        if st.session_state.base_attacks:
            current_max_tick = max(int(a[0]) for a in st.session_state.base_attacks if a)
    cycle_start = ((current_max_tick // 100) + 1) * 100
    cycle_end = cycle_start + 99
    return cycle_start + 1, cycle_end

cycle_start, cycle_end = get_next_cycle_window()

# Generate all 7n+1 ticks within the next cycle window
def generate_7n_plus_1_in_window(start, end):
    ticks = []
    n_start = math.ceil((start - 1) / 7)
    n_end = math.floor((end - 1) / 7)
    for n in range(n_start, n_end + 1):
        candidate = 7 * n + 1
        if start <= candidate <= end:
            ticks.append(candidate)
    return sorted(ticks)

# Show appropriate UI based on multiplayer mode

if "selected_ticks" not in st.session_state:
        st.session_state.selected_ticks = []

if multiplayer_mode:
    
    widget_key = f"tick_selector_{len(st.session_state.selected_ticks)}"
    available_ticks = generate_7n_plus_1_in_window(cycle_start, cycle_end)

    # Show the bank of 7n+1 ticks in the next cycle
    st.write("Select attack ticks (within next cycle):")
    valid_ticks = [tick for tick in st.session_state.selected_ticks if tick in available_ticks]

    new_selection = st.multiselect("Select sequence of attack ticks to optimize", options=sorted(available_ticks), default=valid_ticks, key=widget_key)

    if new_selection != st.session_state.selected_ticks:
        st.session_state.selected_ticks = sorted(new_selection)
        st.rerun()

else:
    # Text input mode
    ticks_input = st.text_input("Sequence of attack ticks to optimize (Comma separated)")
    try:
        input_ticks = [int(t.strip()) for t in ticks_input.split(",") if t.strip().isdigit()]
    except:
        input_ticks = []
    st.session_state.selected_ticks = input_ticks

# Get current attacks considering edits
def get_active_attacks():
    current_df = pd.DataFrame(st.session_state.base_attacks, columns=["Tick", "Percent"])
    if "editor_inside_form" in st.session_state:
        changes = st.session_state["editor_inside_form"]     
        for row_idx in changes.get("deleted_rows", []):
            current_df = current_df.drop(index=row_idx)
        for row_idx, edit in changes.get("edited_rows", {}).items():
            for col, val in edit.items():
                current_df.at[row_idx, col] = val
        for new_row in changes.get("added_rows", []):
            current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
    for col in ["Tick", "Percent"]:
        current_df[col] = pd.to_numeric(current_df[col], errors='coerce')
    return current_df.dropna().values.tolist()

# Run optimizer button
col_opt, col_add = st.columns(2)
with col_opt:
    if st.button("🔍 Run Optimizer", use_container_width=True):
        active_attacks = get_active_attacks()
        with st.spinner("Calculating optimal chain..."):
            results, fail_tick = OptimizeChain(active_attacks, st.session_state.selected_ticks)
            if results:
                st.session_state.optimized_results = results
                sim = OpeningSim(results, verbosity=2)
                f = io.StringIO()
                with redirect_stdout(f):
                    l, t, s = sim.Run(maxTicks=sim_ticks)
                st.session_state.sim_output = {"land": l, "troops": t, "success": s, "log": f.getvalue()}
            else:
                st.error(f"❌ Optimization FAILED at tick {fail_tick}.")
                st.session_state.optimized_results = None
                st.session_state.sim_output = None

# Run manual simulation
if 'run_manual' in locals() and run_manual:
    active_attacks = get_active_attacks()
    sim = OpeningSim(active_attacks, verbosity=2)
    f = io.StringIO()
    with redirect_stdout(f):
        l, t, s = sim.Run(maxTicks=sim_ticks)
    st.session_state.sim_output = {"land": l, "troops": t, "success": s, "log": f.getvalue()}
    st.session_state.optimized_results = None

# Add optimized chain to base attacks
if st.session_state.get('optimized_results'):
    with col_add:
        if st.button("➕ Add to Base Opening", type="primary", use_container_width=True):
            st.session_state.base_attacks = sorted(st.session_state.optimized_results, key=lambda x: x[0])
            st.session_state.optimized_results = None
            st.session_state.sim_output = None
            st.rerun()

# Display results
st.divider()
if st.session_state.get('sim_output'):
    out = st.session_state['sim_output']
    st.subheader("Simulation Results")
    if out["success"]:
        st.success(f"✅ Success! | Final Land: **{out['land']}** | Final Troops: **{out['troops']}**")
    else:
        st.error(f"❌ Failure! | Final Land: **{out['land']}** | Final Troops: **{out['troops']}**")
    with st.expander("View Full Tick-by-Tick Log", expanded=True):
        st.code(out["log"])
