"""
cwl-tes entrypoint script
"""
import sys
import cwl_tes.main

# --tes http://master-node:31567 tests/hashsplitter-workflow.cwl.yml --input tests/resources/test.txt
# --remote-storage-url ftp://10.0.0.10/files/out --insecure --tes http://10.0.0.10:31567 --leave-outputs --debug tests/helm-horovod.cwl.yml tests/inputs.json
#
# sys.argv.append("--remote-storage-url")
# sys.argv.append("ftp://192.168.10.90/files/out")
# sys.argv.append("--insecure")
# sys.argv.append("--tes")
# sys.argv.append("http://192.168.10.90:31567")
# # sys.argv.append("http://192.168.10.90:8080/ga4gh/tes")
# # sys.argv.append("http://10.0.0.10:31568/ga4gh/tes")
# # sys.argv.append("httpu://capoccina:8080")
# sys.argv.append("--leave-outputs")
# sys.argv.append("--debug")
# # sys.argv.append("--enable-ext")
# # sys.argv.append("tests/hashsplitter-workflow_test_file.cwl.yml")
# # sys.argv.append("tests/hashsplitter-workflow.cwl.yml")
#
# # sys.argv.append("tests/hashsplitter-sha.cwl.yml")
# # sys.argv.append("tests/test_from_sha.cwl.yml")
# sys.argv.append("tests/test_from_horo.yml")
#
# sys.argv.append("tests/inputs_test.json")

# print(sys.argv)
# exit()
if __name__ == "__main__":
    sys.exit(
        cwl_tes.main.main(sys.argv[1:])
    )
