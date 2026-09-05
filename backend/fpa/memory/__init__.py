"""Persistent company memory. Same rule as the reference scheduler's caregiver
memory: language may be compiled into structured rows at WRITE time, but run
time reads only plain rows — no model call inside the attribution loop."""
