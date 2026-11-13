import mido
import time

# Alle Ports anzeigen
ports = mido.get_output_names()
print("Verfügbare Outputs:", ports)

# Ersten APC-Port finden (flexibler)
apc_port = None
for p in ports:
    if "apc" in p.lower():
        apc_port = p
        break

if not apc_port:
    print("KEIN APC GEFUNDEN. Prüfe Verkabelung und schließe andere MIDI-Programme.")
    exit(1)

print(f"Öffne: {apc_port}")

with mido.open_output(apc_port) as out:
    # Alle 64 Grid-Pads kurz rot blinken lassen
    for note in range(64):
        out.send(mido.Message("note_on", note=note, velocity=3))
        time.sleep(0.02)
        out.send(mido.Message("note_on", note=note, velocity=0))
    
    # Kurz warten, dann alle wieder an
    time.sleep(0.5)
    for note in range(64):
        out.send(mido.Message("note_on", note=note, velocity=3))
    
    time.sleep(2)
    
    # Alles aus
    for note in range(64):
        out.send(mido.Message("note_on", note=note, velocity=0))

print("Fertig.")