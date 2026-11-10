"""Run the same generator twice and compare row counts and file checksums."""
import argparse, json, tempfile
from pathlib import Path
from src.generator import generate_dataset

def compare(profile="starter", seed=20261022):
    with tempfile.TemporaryDirectory() as tmp:
        a,b=Path(tmp)/"a",Path(tmp)/"b"
        ma=generate_dataset(a,profile,seed)
        mb=generate_dataset(b,profile,seed)
        result={}
        for name,meta in ma["outputs"].items():
            result[name]={"rows_equal":meta["rows"]==mb["outputs"][name]["rows"],
                          "checksum_equal":meta["sha256"]==mb["outputs"][name]["sha256"]}
        return {"reproducible":all(x["rows_equal"] and x["checksum_equal"] for x in result.values()),
                "files":result}
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile",choices=["starter","full"],default="starter")
    ap.add_argument("--seed",type=int,default=20261022)
    a=ap.parse_args()
    print(json.dumps(compare(a.profile,a.seed),indent=2))
