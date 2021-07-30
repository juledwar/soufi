#!groovy

library identifier: 'mylib@master', retriever: legacySCM(scm)

pipeline {
    agent { label 'ci-runner-bionic' }
    environment {
        GITHUB_USER = 'ci-ciscolabs.gen'
    }
    options {
        timeout(time:15, unit: 'MINUTES')
    }
    stages {
        stage('Jenkins build (premerge)') {
            steps {
                buildUtils('postBuildStart', [ issueId: env.ghprbPullId ])
            }
        }
        stage('Build test environment') {
            steps {
                buildUtils('editBuildResult', [ comment: 'Creating venv' ])
                sh(script: 'tools/create-venv')
            }
        }
        stage('Run tests') {
            steps {
                buildUtils('editBuildResult', [ comment: 'Running tox tests' ])
                sh(script: 'tools/run-tests')
                archiveArtifacts artifacts: '.tox/py3/log/*', fingerprint: true, onlyIfSuccessful: false, allowEmptyArchive: true
            }
        }
        stage('Build Python package') {
            steps {
                buildUtils('editBuildResult', [ comment: 'Building python package' ])
                sh(script: 'tools/build-python-package -m premerge')
                script {
                    env.PKG = sh(returnStdout: true,
                                 script: '''
                                         tools/get-package
                                         '''
                                ).trim()
                }
            }
        }
        stage('Publish premerge package to devpi') {
            steps {
                buildUtils('editBuildResult', [ comment: 'Publishing python package' ])
                withCredentials([[$class: 'UsernamePasswordMultiBinding',
                        credentialsId: 'CPSG-soufi-devpi-premerge',
                        usernameVariable: 'USERNAME',
                        passwordVariable: 'PASSWORD']]) {
                    script {
                        env.DEVPI_URL = "https://pypi.ci.ciscolabs.com/" + \
                                        "${USERNAME}/premerge"
                    }
                    sh(script: '''
                               devpi use ${DEVPI_URL}
                               devpi login "${USERNAME}" --password="${PASSWORD}"
                               devpi upload dist/*
                               '''
                      )
                    buildUtils('editBuildResult', [ comment: "Python package ${PKG} published to ${DEVPI_URL}" ])
                }
            }
        }
    }
    post {
        always {
            buildUtils('editBuildResult')
        }
    }
}
