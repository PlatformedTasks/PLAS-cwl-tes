[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# Platformed Task cwl-tes

___cwl-tes___  interpret CWL files and submits tasks to a TES server. 


## Requirements

* Python >= 3.6

## Quickstart

* Install the requirements

```
pip3 install -r requirements.txt
```

* Submit the CWL task or workflow

```
python cwl-tes.py --remote-storage-url ftp://10.0.0.10/files/out --insecure --tes http://10.0.0.10:31567  tests/helm-horovod.cwl.yml --input tests/inputs.txt
```

