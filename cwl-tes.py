"""
cwl-tes entrypoint script
"""
import sys
import cwl_tes.main

if __name__ == "__main__":
    sys.exit(
        cwl_tes.main.main(sys.argv[1:])
    )
