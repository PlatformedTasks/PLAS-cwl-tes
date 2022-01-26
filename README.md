[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# PLAS cwl-tes
In this repository, you can find the instructions to install PLAS-cwl-tes, an extension of the original [cwl-tes](https://github.com/ohsu-comp-bio/cwl-tes). 
The ___cwl-tes___  interpret CWL files and submits tasks to a TES server. 
For a brief introdution to TES head over to the helpful [page](https://github.com/elixir-cloud-aai/TESK/blob/master/documentation/tesintro.md) written by the elixir's team.

PLAS-cwl-tes is an element of the [PLAS project](https://github.com/PlatformedTasks/Documentation) funded by the [GÉANT Innovation Programme](https://community.geant.org/community-programme-portfolio/innovation-programme/) initiative to extend the [GÉANT Cloud Flow (GCF)](https://clouds.geant.org/community-cloud/) to be capable of performing platformed-tasks in the cloud.



## Requirements

* Python >= 3.6

## Quickstart

1. Install the requirements

```
pip3 install -r requirements.txt
```

2. Submit the CWL task or workflow

```
python cwl-tes.py --remote-storage-url ftp://10.0.0.10/files/out --insecure --tes http://10.0.0.10:31567 --leave-outputs tests/helm-horovod.cwl.yml tests/inputs.json
```
