Description
===========

This is a dockerized `Nextflow`_ wrapper that runs a workflow (git repo) on a given `AWS Batch queue`_. There are several options and usage is explained below.

Installation
============

The dockerized version of this application can be pulled directly from ``157538628385.dkr.ecr.us-west-2.amazonaws.com/nextflow_master`` and can be run using ``docker``:

.. code:: console

   $ docker pull 157538628385.dkr.ecr.us-west-2.amazonaws.com/nextflow_master:latest

If access is denied, you may need to log into the ECR registry first 

.. code:: console

    $ $(aws ecr get-login --region us-west-2 --no-include-email)

Documentation
=============

Detailed documentation can be reached at http://nextflow.app.s3-website.us-west-2.amazonaws.com

Example
=======

.. code:: console

    $ docker run --rm -it DOCKER.APP:latest \
    --workflow_id 000001 \
    --queue arn:aws:batch:REGION:ACCOUNT_ID:job-queue/JOB_QUEUE_NAME \
    --project https://github.com/pjongeneel/nextflow_project.git \
    --token XXXXXXXXXXX \
    --work_bucket s3://exampleBucket \
    --configs s3://exampleBucket/sample.1.config s3://exampleBucket/sample.2.config \
    --generate_reports

.. _Nextflow: https://www.nextflow.io/
.. _AWS Batch queue: https://docs.aws.amazon.com/batch/index.html

