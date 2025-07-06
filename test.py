from datasets import load_dataset
from pprint import pprint

swe_bench_dev = load_dataset("princeton-nlp/SWE-bench_Lite", split="dev")
sample_instance = swe_bench_dev[1]
pprint(sample_instance)
print(sample_instance.keys())
print(sample_instance['patch'])
print(sample_instance['test_patch'])
