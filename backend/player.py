from beat_player import pick_voice, play_voice
from drum import DrumSampleLibrary
from pathlib import Path
import sounddevice as sd

SAMPLES_ROOT = Path("Drum").expanduser()

lib = DrumSampleLibrary(SAMPLES_ROOT, seed=42)

class DrumPlayer:
    def __init__(self, sound_master):
        self.sm = sound_master

        self.kick = pick_voice(
            lib,
            name="kick",
            try_queries=[
                # Main kick set: kick_24/kick/kick/k_vl*_rr*.flac
                dict(
                    kit="kick_24",
                    articulation_contains="kick",
                    code="k",
                    prefer_mics=["kick", "oh"],  # leaf folder names seen under kick_24
                    velocity=10,
                    random_choice=True,
                ),

                # Other kick_24 variants: rc/sc/tc have codes like k_rc / k_sc / k_tc with cl/oh
                dict(
                    kit="kick_24",
                    articulation_contains="rc",
                    code_prefix="k_rc",
                    prefer_mics=["cl", "oh"],
                    velocity=4,
                    random_choice=True,
                ),
                dict(
                    kit="kick_24",
                    articulation_contains="sc",
                    code_prefix="k_sc",
                    prefer_mics=["cl", "oh"],
                    velocity=4,
                    random_choice=True,
                ),
                dict(
                    kit="kick_24",
                    articulation_contains="tc",
                    code_prefix="k_tc",
                    prefer_mics=["cl", "oh"],
                    velocity=3,
                    random_choice=True,
                ),

                # No-damp kick: kick_24_nodamp/.../k_nodamp_vl*_rr*.flac
                dict(
                    kit="kick_24_nodamp",
                    code_prefix="k_nodamp",
                    prefer_mics=["kick", "oh"],
                    velocity=4,
                    random_choice=True,
                ),

                # Global fallbacks (if your root differs from the sample tree)
                dict(
                    kit=None,
                    code="k",
                    prefer_mics=["kick", "cl", "oh"],
                    random_choice=True,
                ),
                dict(
                    kit=None,
                    code_prefix="k_",
                    prefer_mics=["kick", "cl", "oh"],
                    random_choice=True,
                ),
            ],
        )

        self.snare = pick_voice(
            lib,
            name="snare",
            try_queries=[
                # If you have kits with plain sn_vl*_rr*.flac (e.g. 14d_basic, 14p_basic), this will work:
                dict(
                    kit=None,
                    code="sn",
                    prefer_mics=["top", "oh", "btm", "out"],
                    velocity=7,
                    random_choice=True,
                ),

                # Your snare_14 uses codes like sn_bdig / sn_flutter, so match by prefix:
                dict(
                    kit="snare_14",
                    articulation_contains="edge",     # prefer the standard hit set
                    code_prefix="sn_",
                    prefer_mics=["top", "oh", "btm"],
                    velocity=7,                       # maps to nearest available layer
                    random_choice=True,
                ),

                # Final fallback: any snare_14 articulation with sn_ prefix
                dict(
                    kit="snare_14",
                    code_prefix="sn_",
                    prefer_mics=["top", "oh", "btm"],
                    random_choice=True,
                ),
            ],
        )

        self.hat = pick_voice(
            lib,
            name="hat",
            try_queries=[
                # Prefer the standard chick set: hihat_14/chik/(cl|oh)/ht_chik_vl*_rr*.flac
                dict(
                    kit="hihat_14",
                    articulation_contains="chik",
                    code_prefix="ht_chik",
                    prefer_mics=["cl", "oh"],
                    velocity=5,
                    random_choice=True,
                ),

                # Any hat in hihat_14 (covers other ht_* sets like ht_tc_s, etc.)
                dict(
                    kit="hihat_14",
                    code_prefix="ht_",
                    prefer_mics=["cl", "oh"],
                    velocity=5,
                    random_choice=True,
                ),

                # Global fallback: any kit that has ht_* hats
                dict(
                    kit=None,
                    code_prefix="ht_",
                    prefer_mics=["cl", "oh", "top", "btm"],
                    random_choice=True,
                ),
            ],
        )
        
        self.tom = pick_voice(
            lib,
            name="tom",
            try_queries=[
                dict(
                    kit="tom_14",
                    articulation="brush",
                    mic="cl",        # or "oh"
                    code="t14_b",    # matches t14_b_vl*_rr*.flac
                ),
                dict(
                    kit="tom_15",
                    articulation="sc",
                    mic="oh",        # or "cl"
                    code="t15_sc",   # matches t15_sc_vl*_rr*.flac
                ),
            ],
        )

        self.voices = {"kick": self.kick, "snare": self.snare, "hat": self.hat, "tom": self.tom}

    def play(self, voice_name):
        if voice_name in self.voices:
            voice = self.voices[voice_name]
            if voice:
                play_voice(voice, sound_master=self.sm)
            else:
                print(f"No sample found for {voice_name}")
        else:
            print(f"Unknown voice: {voice_name}")
