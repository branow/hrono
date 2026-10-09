hrono cli

- server (hrono server)

    start server on port 8080, expose rest api.
    web ui

- client
    http client to the server


Rest API

- Register sources, where system can get data from, each sources will have unique name, to reference it.
/sources (GET, POST)
/sources/<source> (GET, PUT, DELETE)


GET /connections
POST /connections
GET /connections/<name>
PUT /connections/<name>
DELETE /connections/<name>
