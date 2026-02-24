"""
╔══════════════════════════════════════════════════╗
║          GALDR ENGINE – EKOKAMMAREN              ║
║     Malmös Osynliga Röster (Terminal PoC)        ║
╚══════════════════════════════════════════════════╝

Kör:  python play.py
      python play.py --api-key sk-...   (med OpenAI för AI-svar)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Lägg till app/ i path
sys.path.insert(0, str(Path(__file__).parent))

from galdr.core.engine import GaldrEngine
from galdr.core.nodes import Scenario
from galdr.config import settings
from galdr.services.openai_service import OpenAIService


# ---------------------------------------------------------------------------
# Terminalgrafik
# ---------------------------------------------------------------------------

CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
RESET = "\033[0m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"


def style_narrator(text: str) -> str:
    return f"{CYAN}{ITALIC}{text}{RESET}"


def style_system(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def style_action(idx: int, label: str) -> str:
    return f"  {YELLOW}[{idx}]{RESET} {label}"


def style_dice(text: str) -> str:
    return f"{MAGENTA}{text}{RESET}"


def style_hp(current: int, maximum: int) -> str:
    ratio = current / maximum if maximum > 0 else 0
    color = GREEN if ratio > 0.5 else YELLOW if ratio > 0.25 else RED
    bar_len = 20
    filled = int(ratio * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    return f"{color}{bar} {current}/{maximum} HP{RESET}"


def print_header():
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════╗
║  {BOLD}G A L D R{RESET}{CYAN}  –  E K O K A M M A R E N              ║
║  {DIM}Malmös Osynliga Röster{RESET}{CYAN}                             ║
╚══════════════════════════════════════════════════════╝{RESET}
""")


def print_divider():
    print(f"{DIM}{'─' * 56}{RESET}")


def print_status(state):
    items = ", ".join(i.name for i in state.character.inventory) or "Inget"
    node_title = state.current_node_id
    flags_count = len(state.narrative_flags.flags)

    print(f"\n{DIM}┌─ Status ────────────────────────────────────────┐{RESET}")
    print(f"{DIM}│{RESET}  {style_hp(state.character.hp, state.character.max_hp)}")
    print(f"{DIM}│{RESET}  {WHITE}Föremål:{RESET} {items}")
    print(f"{DIM}│{RESET}  {WHITE}Plats:{RESET}   {node_title}  {DIM}(tur {state.turn_count}){RESET}")
    print(f"{DIM}└─────────────────────────────────────────────────┘{RESET}")


# ---------------------------------------------------------------------------
# Huvudloop
# ---------------------------------------------------------------------------

async def play():
    parser = argparse.ArgumentParser(description="GALDR Ekokammaren – Terminal PoC")
    parser.add_argument("--api-key", help="OpenAI API-nyckel för AI-genererade svar")
    parser.add_argument("--name", default="", help="Karaktärsnamn")
    args = parser.parse_args()

    if args.api_key:
        settings.openai_api_key = args.api_key
        os.environ["OPENAI_API_KEY"] = args.api_key

    # Ladda scenario
    scenario_path = Path(__file__).parent / "scenarios" / "ekokammaren.json"
    if not scenario_path.exists():
        print(f"{RED}Scenariot hittades inte: {scenario_path}{RESET}")
        return

    scenario = Scenario.load_from_file(scenario_path)
    
    # Initialize Services
    ai_service = OpenAIService(
        api_key=settings.openai_api_key, 
        model=settings.openai_model
    )
    
    engine = GaldrEngine(
        scenario=scenario,
        llm=ai_service,
        tts=ai_service
    )

    # Intro
    print(CLEAR)
    print_header()

    if settings.openai_api_key:
        print(style_system("  [AI-läge: OpenAI aktivt – dynamiska svar]"))
    else:
        print(style_system("  [Offline-läge: Skriptade svar från scenariot]"))
        print(style_system("  Kör med --api-key sk-... för AI-genererade svar"))

    print()
    print_divider()
    print()

    # Karaktärsnamn
    name = args.name
    if not name:
        print(f"{WHITE}Vad heter du, vandrare?{RESET}")
        print(f"{DIM}(Tryck Enter för 'Äventyrare'){RESET}")
        try:
            name = input(f"\n{YELLOW}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not name:
            name = "Äventyrare"

    state = engine.create_session(name)
    print()
    print(style_system(f"  Välkommen, {name}. Berättelsen börjar..."))
    print()
    print_divider()

    # Enter first node
    response = await engine.enter_node(state.session_id)
    print()
    print(style_narrator(response.text))

    # Visa state-ändringar
    for change in response.state_changes:
        if change:
            print(f"  {GREEN}> {change}{RESET}")

    # Game loop
    while True:
        state = engine.get_session(state.session_id)
        if not state:
            break

        # Kolla om vi nått ett slut
        node = scenario.get_node(state.current_node_id)
        if node and node.id in scenario.end_nodes:
            print()
            print_divider()
            print()
            print(style_system("  ── SLUT ──"))
            print()

            # Visa sluttext om vi inte redan gjort det
            if not any(e.node_id == node.id for e in state.dialog_history[:-1]):
                end_response = await engine.enter_node(state.session_id)
                print(style_narrator(end_response.text))

            print()
            print_status(state)
            print()

            # Sammanfattning
            locations_visited = sum(
                1 for loc in state.world.locations.values() if loc.visited
            )
            items = len(state.character.inventory)
            print(style_system(f"  Platser besökta: {locations_visited}/{len(scenario.nodes)}"))
            print(style_system(f"  Föremål samlade: {items}"))
            print(style_system(f"  Turer: {state.turn_count}"))

            ending = state.narrative_flags.get_flag("ending", "okänt")
            if ending == "ljus":
                print(f"\n  {GREEN}{BOLD}Slut: Ljuset återvänder{RESET}")
            elif ending == "mörker":
                print(f"\n  {RED}{BOLD}Slut: Skuggorna stannar{RESET}")

            print()
            print(style_system("  Tack för att du spelade Ekokammaren."))
            print(style_system("  GALDR Engine PoC v0.1.0"))
            print()
            break

        # Visa actions
        available = response.available_actions
        if available:
            print()
            for i, action in enumerate(available, 1):
                print(style_action(i, action["label"]))
            print()

        # Spelarens input
        try:
            player_input = input(f"{YELLOW}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Berättelsen pausas...{RESET}")
            break

        if not player_input:
            continue

        # Specialkommandon
        if player_input.lower() in ("quit", "exit", "q", "avsluta"):
            print(f"\n{DIM}Du lämnar berättelsen...{RESET}")
            break
        if player_input.lower() in ("status", "s", "stats"):
            print_status(state)
            continue
        if player_input.lower() in ("help", "h", "hjälp", "?"):
            print()
            print(style_system("  Kommandon:"))
            print(style_system("    [1-9]    Välj handling"))
            print(style_system("    status   Visa karaktärsstatus"))
            print(style_system("    quit     Avsluta"))
            print(style_system("    hjälp    Visa denna hjälp"))
            print(style_system("  Eller skriv fritt vad du vill göra!"))
            print()
            continue

        # Processa input
        print()
        prev_node = state.current_node_id
        response = await engine.process_input(state.session_id, player_input)

        # Tärningsresultat
        if response.dice_result:
            dr = response.dice_result
            roll_str = f"d20: {dr.roll.rolls[0]}"
            if dr.ability_modifier != 0:
                sign = "+" if dr.ability_modifier > 0 else ""
                roll_str += f" {sign}{dr.ability_modifier}"
            roll_str += f" = {dr.total} mot DC {dr.dc}"

            if dr.critical_success:
                print(style_dice(f"  ⚄ KRITISK FRAMGÅNG! [{roll_str}]"))
            elif dr.critical_failure:
                print(style_dice(f"  ⚀ KRITISKT MISSLYCKANDE! [{roll_str}]"))
            elif dr.success:
                print(style_dice(f"  ⚃ Lyckat! [{roll_str}]"))
            else:
                print(style_dice(f"  ⚁ Misslyckat [{roll_str}]"))
            print()

        # Nod-byte
        state = engine.get_session(state.session_id)
        if state.current_node_id != prev_node:
            new_node = scenario.get_node(state.current_node_id)
            if new_node:
                print_divider()
                print(f"\n  {BLUE}{BOLD}{new_node.title}{RESET}\n")

                # Hämta opening text för den nya noden
                enter_response = await engine.enter_node(state.session_id)
                print(style_narrator(enter_response.text))

                for change in enter_response.state_changes:
                    if change:
                        print(f"  {GREEN}> {change}{RESET}")

                # Uppdatera response med nya nodens actions
                response = enter_response
        else:
            # Visa AI-svar (samma nod)
            if response.text:
                print(style_narrator(response.text))

        # State changes
        for change in response.state_changes:
            if change:
                print(f"  {GREEN}> {change}{RESET}")


def main():
    try:
        asyncio.run(play())
    except KeyboardInterrupt:
        print(f"\n{DIM}Avbrutet.{RESET}")


if __name__ == "__main__":
    main()
