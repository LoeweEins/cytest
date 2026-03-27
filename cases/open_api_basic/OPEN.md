** 用开源 api 站点测试的
1–20：Posts（20 条）
#0001：GET /posts/1
#0002：GET /posts/2
#0003：GET /posts/3
#0004：GET /posts/4
#0005：GET /posts/5
#0006：GET /posts/6
#0007：GET /posts/7
#0008：GET /posts/8
#0009：GET /posts/9
#0010：GET /posts/10
#0011：GET /posts/11
#0012：GET /posts/12
#0013：GET /posts/13
#0014：GET /posts/14
#0015：GET /posts/15
#0016：GET /posts/16
#0017：GET /posts/17
#0018：GET /posts/18
#0019：GET /posts/19
#0020：GET /posts/20
断言字段（posts）：userId, id, title, body

21–40：Comments（20 条）
#0021：GET /comments/1
#0022：GET /comments/2
#0023：GET /comments/3
#0024：GET /comments/4
#0025：GET /comments/5
#0026：GET /comments/6
#0027：GET /comments/7
#0028：GET /comments/8
#0029：GET /comments/9
#0030：GET /comments/10
#0031：GET /comments/11
#0032：GET /comments/12
#0033：GET /comments/13
#0034：GET /comments/14
#0035：GET /comments/15
#0036：GET /comments/16
#0037：GET /comments/17
#0038：GET /comments/18
#0039：GET /comments/19
#0040：GET /comments/20
断言字段（comments）：postId, id, name, email, body

41–60：Albums（20 条）
#0041：GET /albums/1
#0042：GET /albums/2
#0043：GET /albums/3
#0044：GET /albums/4
#0045：GET /albums/5
#0046：GET /albums/6
#0047：GET /albums/7
#0048：GET /albums/8
#0049：GET /albums/9
#0050：GET /albums/10
#0051：GET /albums/11
#0052：GET /albums/12
#0053：GET /albums/13
#0054：GET /albums/14
#0055：GET /albums/15
#0056：GET /albums/16
#0057：GET /albums/17
#0058：GET /albums/18
#0059：GET /albums/19
#0060：GET /albums/20
断言字段（albums）：userId, id, title

61–80：Photos（20 条）
#0061：GET /photos/1
#0062：GET /photos/2
#0063：GET /photos/3
#0064：GET /photos/4
#0065：GET /photos/5
#0066：GET /photos/6
#0067：GET /photos/7
#0068：GET /photos/8
#0069：GET /photos/9
#0070：GET /photos/10
#0071：GET /photos/11
#0072：GET /photos/12
#0073：GET /photos/13
#0074：GET /photos/14
#0075：GET /photos/15
#0076：GET /photos/16
#0077：GET /photos/17
#0078：GET /photos/18
#0079：GET /photos/19
#0080：GET /photos/20
断言字段（photos）：albumId, id, title, url, thumbnailUrl

81–90：Users（10 条）
#0081：GET /users/1
#0082：GET /users/2
#0083：GET /users/3
#0084：GET /users/4
#0085：GET /users/5
#0086：GET /users/6
#0087：GET /users/7
#0088：GET /users/8
#0089：GET /users/9
#0090：GET /users/10
断言字段（users）：id, name, username, email

91–100：Todos（10 条）
#0091：GET /todos/1
#0092：GET /todos/2
#0093：GET /todos/3
#0094：GET /todos/4
#0095：GET /todos/5
#0096：GET /todos/6
#0097：GET /todos/7
#0098：GET /todos/8
#0099：GET /todos/9
#0100：GET /todos/10
断言字段（todos）：userId, id, title, completed

101–107（来自 rest_routes_cases.py，按文档 Routes 覆盖）
#0101：GET /posts（获取 posts 列表）
#0102：GET /posts/1/comments（嵌套资源：某 post 的 comments）
#0103：GET /comments?postId=1（查询参数过滤）
#0104：POST /posts（创建资源，期望 201）
#0105：PUT /posts/1（整体更新，期望 200）
#0106：PATCH /posts/1（部分更新，期望 200）
#0107：DELETE /posts/1（删除，期望 200）