import argparse
import subprocess
import sys
import time

def run_step(name: str, cmd: list[str]) -> None:
    print(f"\n{'='*50}")
    print(f"🚀 Starting step: {name}")
    print(f"{'='*50}")
    
    start_time = time.time()
    try:
        # Run command, redirecting stdout/stderr to the console
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Step '{name}' failed with exit code {e.returncode}.")
        sys.exit(1)
        
    duration = time.time() - start_time
    print(f"\n✅ Step '{name}' completed successfully in {duration:.2f}s.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full FHIRGraph pipeline.")
    parser.add_argument("--patients", type=int, default=100, help="Number of patients to generate")
    parser.add_argument("--seed", type=int, default=20260830, help="Random seed for generation")
    args = parser.parse_args()

    print("=== FHIRGraph Full Pipeline Orchestration ===")
    print(f"Settings: Patients={args.patients}, Seed={args.seed}")
    overall_start = time.time()

    steps = [
        (sys.executable, "-m", "pipelines.generate", "--patients", str(args.patients), "--seed", str(args.seed)),
        (sys.executable, "-m", "pipelines.load_fhir"),
        (sys.executable, "-m", "pipelines.build_graph"),
        (sys.executable, "-m", "pipelines.reconcile"),
    ]

    for name, cmd in [
        ("Generate Synthetic Data", list(steps[0])),
        ("Load FHIR to HAPI", list(steps[1])),
        ("Build Knowledge Graph", list(steps[2])),
        ("Reconcile FHIR", list(steps[3])),
    ]:
        run_step(name, cmd)

    total_duration = time.time() - overall_start
    print(f"🎉 Pipeline finished successfully in {total_duration:.2f}s!")

if __name__ == "__main__":
    main()
