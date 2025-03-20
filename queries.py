
Q_CHECK_COMMANDS = """
            query($owner:String!, $repo:String!, $issueNumber:Int!) {
                repository(owner:$owner, name:$repo) {
                    issue(number:$issueNumber) {
                    title
                    body
                    comments(last:10) {
                        nodes {
                            id
                            body
                            createdAt
                        }
                    }
                }
            }
        """