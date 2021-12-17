"""
cwl-tes entrypoint script
"""
import sys
import cwl_tes.main

# --tes http://master-node:31567 tests/hashsplitter-workflow.cwl.yml --input tests/resources/test.txt
sys.argv.append("--remote-storage-url")
sys.argv.append("ftp://10.0.0.10/files/out")
sys.argv.append("--insecure")
sys.argv.append("--tes")
sys.argv.append("http://10.0.0.10:31567")
sys.argv.append("--leave-outputs")
sys.argv.append("--debug")
# sys.argv.append("tests/hashsplitter-workflow.cwl.yml")
# sys.argv.append("tests/hashsplitter-sha.cwl.yml")
sys.argv.append("tests/helm-horovod.cwl.yml")
sys.argv.append("tests/inputs.json")


if __name__ == "__main__":
    sys.exit(
        cwl_tes.main.main(sys.argv[1:])
    )
