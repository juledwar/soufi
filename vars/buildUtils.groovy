def call(cmd, Map args = [:]) {

    switch (cmd) {
    case 'findIssueFromMerge' :
        findIssueFromMerge(args)
        break
    case 'findIssueFromLabel' :
        findIssueFromLabel(args)
        break
    case 'postIssueComment' :
        postIssueComment(args)
        break
    case 'editComment' :
        editComment(args)
        break
    case 'postBuildStart' :
        postBuildStart(args)
        break
    case 'postBuildResult' :
        postBuildResult(args)
        break
    case 'editBuildResult' :
        editBuildResult(args)
        break
    default:
        break
    }
}


def postBuildStart(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'issueId' ],
                    [ name : 'buildJobName' ],
                    [ name : 'ghCommit' ],
                    [ name : 'commentVar' ],
                    [ name : 'addTimeStamp' ] ]

    println('In postBuildStart')
    args = processArgs(args, params)
    if (args.issueId != null && args.issueId != '') {
        if (args.comment == null || args.comment == '') {
            args.comment = "CI starting ${args.buildJobName} " + \
                           "[build](${env.BUILD_URL}) for " + \
                           "commit ${args.ghCommit} ..."
        }
        postIssueComment(args)
    }
}


def postBuildResult(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'issueId' ],
                    [ name : 'buildJobName' ],
                    [ name : 'ghCommit' ],
                    [ name : 'commentVar' ],
                    [ name : 'addTimeStamp' ] ]

    println('In postBuildResult')
    args = processArgs(args, params)
    if (args.issueId != null && args.issueId != '') {
        if (args.comment == null || args.comment == '') {
            if (args.buildResult == 'SUCCESS') {
                args.comment = ":white_check_mark: " + \
                               "${args.buildJobName} [build](${BUILD_URL}) " + \
                               "succeeded for commit ${args.ghCommit}"
            } else {
                args.comment = ":x: ${args.buildJobName} " + \
                               "[build](${BUILD_URL}) failed for commit " + \
                               "${args.ghCommit}"
            }
        }
        postIssueComment(args)
    }
}


def editBuildResult(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'commentId' ],
                    [ name : 'buildJobName' ],
                    [ name : 'ghCommit' ],
                    [ name : 'buildResult' ],
                    [ name : 'commentSep' ],
                    [ name : 'addTimeStamp' ] ]

    println('In editBuildResult')
    args = processArgs(args, params)
    if (args.commentId != null && args.commentId != '') {
        if (args.comment == null || args.comment == '') {
            if (args.buildResult == 'SUCCESS') {
                args.comment = ":white_check_mark: " + \
                               "${args.buildJobName} [build](${BUILD_URL}) " + \
                               "succeeded for commit ${args.ghCommit}"
            } else {
                args.comment = ":x: ${args.buildJobName} " + \
                               "[build](${BUILD_URL}) failed for commit " + \
                               "${args.ghCommit}"
            }
        }
        appendComment(args)
    }
}


String getComment(Map args) {
    List params = [ [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'commentId' ] ]

    println('In getComment')
    args = processArgs(args, params)
    String comment
    if (args.commentId != null && args.commentId != '') {
        withCredentials([[$class: 'StringBinding',
                          credentialsId: args.credentialsId,
                          variable: 'POLARIS_GITHUB_TOKEN']]) {
            String auth = "${args.ghUser}:${env.POLARIS_GITHUB_TOKEN}"
            String url = "https://${args.ghHost}/api/v3/repos/${args.repo}" + \
                         "/issues/comments/${args.commentId}"
            String python_cmd = """import json,sys; """ + \
                                """d = json.load(sys.stdin); """ + \
                                """print("%s" % (d["body"]))"""
            comment = sh(returnStdout: true,
                         script: """
                                 curl --request GET --user '${auth}' '${url}' | \
                                 python3 -c '${python_cmd}'
                                 """
                        ).trim()
        }
    }
    return comment
}


def editComment(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'commentId' ],
                    [ name : 'addTimeStamp' ] ]

    println('In editComment')
    args = processArgs(args, params)
    if (args.commentId != null  && args.commentId != '') {
        String date_string = ''
        if (args.addTimeStamp) {
            def date = new Date()
            date_string = "[${date}] "
        }
        args.comment = date_string + args.comment
        def jstring = """'''{ "body": "${args.comment}" }'''"""
        withCredentials([[$class: 'StringBinding',
                          credentialsId: args.credentialsId,
                          variable: 'POLARIS_GITHUB_TOKEN']]) {
            String auth = "${args.ghUser}:${env.POLARIS_GITHUB_TOKEN}"
            String url = "https://${args.ghHost}/api/v3/repos/${args.repo}" + \
                         "/issues/comments/${args.commentId}"
            sh(script: """
                       curl --request PATCH --user '${auth}' \
                        -d $jstring '${url}'
                       """
              )
        }
    }
}


def appendComment(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'commentId' ],
                    [ name : 'addTimeStamp' ] ]

    println('In appendComment')
    args = processArgs(args, params)
    if (args.commentId != null  && args.commentId != '') {
        String date_string = ''
        if (args.addTimeStamp) {
            def date = new Date()
            date_string = "[${date}] "
            args.addTimeStamp = false
        }
        String origComment
        origComment = getComment(args)
        if (origComment != null) {
            println("found ORIG: ${origComment}")
            args.comment = origComment + args.commentSep + \
                           date_string + args.comment
        } else {
            args.comment = date_string + args.comment
        }
        editComment(args)
    }
}


def postIssueComment(Map args) {
    List params = [ [ name : 'comment' ],
                    [ name : 'credentialsId' ],
                    [ name : 'ghUser' ],
                    [ name : 'ghHost' ],
                    [ name : 'repo' ],
                    [ name : 'issueId' ],
                    [ name : 'commentVar' ],
                    [ name : 'addTimeStamp' ] ]

    println('In postIssueComment')
    args = processArgs(args, params)
    if (args.issueId != null  && args.issueId != '') {
        if (args.addTimeStamp) {
            def date = new Date()
            args.comment = "[${date}] ${args.comment}"
        }
        def jstring = """'''{ "body": "${args.comment}" }'''"""
        withCredentials([[$class: 'StringBinding',
                          credentialsId: args.credentialsId,
                          variable: 'POLARIS_GITHUB_TOKEN']]) {
            String auth = "${args.ghUser}:${env.POLARIS_GITHUB_TOKEN}"
            String url = "https://${args.ghHost}/api/v3/repos/${args.repo}" + \
                         "/issues/${args.issueId}/comments"
            String python_cmd = """import json,sys; """ + \
                                """d = json.load(sys.stdin); """ + \
                                """print("%s" % (d["id"]))"""
            String commentId
            commentId = sh(returnStdout: true,
                           script: """
                                   curl --request POST --user '${auth}' \
                                       -d $jstring '${url}' | \
                                   python3 -c '${python_cmd}'
                                   """
                          ).trim()
            env[(args.commentVar)] = commentId
        }
    }
}


def findIssueFromLabel(Map args) {
    List params = [ [ name : 'credentialsId'],
                    [ name : 'ghCommit' ],
                    [ name : 'ghUser' ],
                    [ name : 'repo' ],
                    [ name : 'ghHost' ],
                    [ name : 'labels' ],
                    [ name : 'issueVar' ] ]

    println('In findIssueFromLabel')
    args = processArgs(args, params)
    withCredentials([[$class: 'StringBinding',
                      credentialsId: args.credentialsId,
                      variable: 'POLARIS_GITHUB_TOKEN']]) {
        String auth = "${args.ghUser}:${env.POLARIS_GITHUB_TOKEN}"
        String url = "https://${args.ghHost}/api/v3/repos/${args.repo}" + \
                     "/issues?labels=${args.labels}&state=open&" + \
                     "sort=created&direction=desc"
        String python_cmd = """import json,sys; """ + \
                            """d = json.load(sys.stdin); """ + \
                            """a = [ i["number"] for i in d ]; """ + \
                            """a.append(""); """ + \
                            """print("%s" % (a[0]))"""
        String issueId
        issueId = sh(returnStdout: true,
                     script: """
                             curl --user '${auth}' '${url}' | \
                             python3 -c '${python_cmd}'
                             """
                    ).trim()
        env[(args.issueVar)] = issueId
    }
}


def findIssueFromMerge(Map args) {
    List params = [ [ name : 'credentialsId'],
                    [ name : 'ghCommit' ],
                    [ name : 'ghUser' ],
                    [ name : 'repo' ],
                    [ name : 'ghHost' ],
                    [ name : 'issueVar' ] ]

    println('In findIssueFromMerge')
    args = processArgs(args, params)
    withCredentials([[$class: 'StringBinding',
                      credentialsId: args.credentialsId,
                      variable: 'POLARIS_GITHUB_TOKEN']]) {
        String auth = "${args.ghUser}:${env.POLARIS_GITHUB_TOKEN}"
        String url = "https://${args.ghHost}/api/v3/repos/${args.repo}" + \
                     "/pulls?state=closed&sort=updated&direction=desc"
        String python_cmd = """import json,sys; """ + \
                            """d = json.load(sys.stdin); """ + \
                            """a = [ i["issue_url"].rpartition("/")[2] for i in d if i["merge_commit_sha"] == "${args.ghCommit}" ]; """ + \
                            """a.append(""); """ + \
                            """print("%s" % (a[0]))"""
        String issueId
        issueId = sh(returnStdout: true,
                     script: """
                             curl --user '${auth}' '${url}' | \
                             python3 -c '${python_cmd}'
                             """
                    ).trim()
        env[(args.issueVar)] = issueId
    }
}


def processArgs(Map args, List params) {
    println('In processArgs.call')

    def newargs = [:]

    // Fill newargs with expected params and their default values
    for (p in params) {
        newargs[(p.name)] = p.default ?: getDefault(p.name)
    }
    // Overwrite param default values with values passed in
    for (a in args) {
        newargs[(a.key)] = a.value
    }
    return newargs
}


def getDefault(param) {
    switch (param) {
    case 'credentialsId':
        return 'github-engit-ci-ciscolabs-gen-token'
    case 'ghUser':
        return env.GITHUB_USER
    case 'ghHost':
        return 'wwwin-github.cisco.com'
    case 'ghMerge':
        return env.GIT_COMMIT
    case 'issueId':
        return env.ISSUE_ID
    case 'repo':
        return env.GIT_URL - ~/^.*:/ - ~/(?i)\.git$/
    case 'inProgress':
        return false
    case 'issueVar':
        return 'ISSUE_ID'
    case 'commentVar':
        return 'COMMENT_ID'
    case 'commentId':
        return env.COMMENT_ID
    case 'labels':
        return env.JOB_BASE_NAME
    case 'ghCommit':
        if (env.JOB_BASE_NAME == 'recheck') {
            return env.ghprbActualCommit
        }
        return env.GIT_COMMIT
    case 'buildJobName':
        return env.JOB_BASE_NAME
    case 'buildResult':
        return currentBuild.currentResult
    case 'commentSep':
        return '<br/>'
    case 'addTimeStamp':
        return true
    default:
        return null
    }
}
