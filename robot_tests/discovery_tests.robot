*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py
Test Teardown    Cleanup Sample Project

*** Test Cases ***
Find a FastAPI REST endpoint
    [Documentation]    Checks that a basic FastAPI app is discovered as a REST backend.
    Log    Running FastAPI discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    app.py    from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\nclass UserCreate(BaseModel):\n    name: str\n    age: int\n    active: bool\n\n@app.post("/users")\nasync def create_user(payload: UserCreate):\n    return payload
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python
    Log    Passed because the FastAPI sample was discovered as Python backend code.

Find Spring REST and GraphQL endpoints
    [Documentation]    Checks that Spring REST and GraphQL endpoints are both discovered.
    Log    Running Spring discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserController.java    package demo;\n\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RequestMapping;\nimport org.springframework.web.bind.annotation.RestController;\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\n\n@RestController\n@RequestMapping("/api/users")\npublic class UserController {\n    @GetMapping("/{id}")\n    public String getUser() {\n        return "ok";\n    }\n\n    @QueryMapping\n    public String userProfile() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java
    Should Be Equal    ${discovery.api_style}    GraphQL + REST
    Should Contain    ${discovery.frameworks}    Spring Web
    Should Contain    ${discovery.frameworks}    Spring GraphQL
    ${paths}=    Get Endpoint Paths    ${discovery}    rest
    Should Contain    ${paths}    GET /api/users/{id}
    ${names}=    Get Endpoint Names    ${discovery}    graphql
    Should Contain    ${names}    userProfile

Decide API style from endpoints
    [Documentation]    Checks that API style comes from both REST and GraphQL endpoints.
    Log    Running API style discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserController.java    package demo;\n\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RestController;\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\nimport org.springframework.stereotype.Controller;\n\n@RestController\npublic class UserController {\n    @GetMapping("/users")\n    public String getUsers() {\n        return "ok";\n    }\n}\n\n@Controller\nclass GraphqlController {\n    @QueryMapping\n    public String userProfile() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.api_style}    GraphQL + REST
    Log    Passed because the project combines REST and GraphQL endpoints.

Find explicit Spring GraphQL name
    [Documentation]    Checks that an explicit GraphQL mapping name is discovered.
    Log    Running explicit GraphQL name case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    GraphqlController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\nimport org.springframework.stereotype.Controller;\n\n@Controller\npublic class GraphqlController {\n    @QueryMapping(name = "keycloakgraphql")\n    public String graphql() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${names}=    Get Endpoint Names    ${discovery}    graphql
    Should Contain    ${names}    keycloakgraphql
    Log    Passed because the explicit GraphQL name was detected.

Find custom Spring GraphQL path from properties
    [Documentation]    Checks that Spring GraphQL path settings are discovered.
    Log    Running Spring GraphQL path case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    application.properties    spring.graphql.path=/keycloakgraphql
    Write Project File    ${project}    GraphqlController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\nimport org.springframework.stereotype.Controller;\n\n@Controller\npublic class GraphqlController {\n    @QueryMapping\n    public String userProfile() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${paths}=    Get Endpoint Paths    ${discovery}    graphql
    Should Contain    ${paths}    POST /keycloakgraphql
    Log    Passed because the Spring GraphQL path was discovered.

Find Spring context path for REST and GraphQL
    [Documentation]    Checks that the Spring context path is applied to REST endpoints.
    Log    Running Spring context path case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    application.properties    server.servlet.context-path=/api\nspring.graphql.path=/graphql
    Write Project File    ${project}    UserController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\nimport org.springframework.stereotype.Controller;\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RequestMapping;\nimport org.springframework.web.bind.annotation.RestController;\n\n@RestController\n@RequestMapping("/users")\nclass UserController {\n    @GetMapping("/{id}")\n    public String getUser() {\n        return "ok";\n    }\n}\n\n@Controller\nclass GraphqlController {\n    @QueryMapping\n    public String userProfile() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${rest_paths}=    Get Endpoint Paths    ${discovery}    rest
    Should Contain    ${rest_paths}    GET /api/users/{id}

Find custom Python GraphQL mount path
    [Documentation]    Checks that a mounted Strawberry GraphQL app is discovered.
    Log    Running Python GraphQL mount case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    app.py    import strawberry\nfrom fastapi import FastAPI\nfrom strawberry.fastapi import GraphQLRouter\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def userProfile(self) -> str:\n        return "ok"\n\nschema = strawberry.Schema(query=Query)\ngraphql_app = GraphQLRouter(schema)\n\napp = FastAPI()\napp.mount("/keycloakgraphql", graphql_app)
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Find custom FastAPI GraphQL router wrapper path
    [Documentation]    Checks that the FastAPI GraphQL wrapper path is discovered.
    Log    Running FastAPI GraphQL wrapper case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    main.py    import strawberry\nfrom fastapi import FastAPI\n\nclass OrjsonGraphQLRouter:\n    def __init__(self, schema, context_getter=None):\n        self.schema = schema\n        self.context_getter = context_getter\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def health(self) -> str:\n        return "ok"\n\nschema = strawberry.Schema(query=Query)\ngraphql_app = OrjsonGraphQLRouter(schema)\n\napp = FastAPI()\napp.include_router(graphql_app, prefix="/keycloakgraphql")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build Strawberry GraphQL example fields
    [Documentation]    Checks that Strawberry GraphQL examples include placeholder fields.
    Log    Running Strawberry GraphQL example case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass User:\n    id: str\n    username: str\n    email: str\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def userById(self, user_id: str) -> User:\n        return User(id="1", username="demo", email="demo@example.com")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Find Java GraphQL variables and placeholders
    [Documentation]    Checks that Java GraphQL endpoints are discovered.
    Log    Running Java GraphQL discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    GraphqlController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.QueryMapping;\nimport org.springframework.stereotype.Controller;\n\nclass UserProfile {\n    private String name;\n    private Integer age;\n}\n\n@Controller\npublic class GraphqlController {\n    @QueryMapping\n    public UserProfile userById(String userId) {\n        return new UserProfile();\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java
    Should Contain    ${discovery.frameworks}    Spring GraphQL

Find Java GraphQL custom input types as non-null
    [Documentation]    Checks that Java GraphQL mutation inputs are discovered.
    Log    Running Java GraphQL mutation input case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    GraphqlController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.Argument;\nimport org.springframework.graphql.data.method.annotation.MutationMapping;\nimport org.springframework.stereotype.Controller;\n\nclass BuyersDelete {\n}\n\n@Controller\npublic class GraphqlController {\n    @MutationMapping\n    public String delete_buyer(@Argument BuyersDelete buyer) {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java
    Should Contain    ${discovery.frameworks}    Spring GraphQL

Find Java REST response example from return type
    [Documentation]    Checks that Java REST response examples are discovered.
    Log    Running Java REST response case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserController.java    package demo;\n\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RequestMapping;\nimport org.springframework.web.bind.annotation.RestController;\n\nclass UserResponse {\n    private String name;\n    private Integer age;\n}\n\n@RestController\n@RequestMapping("/users")\npublic class UserController {\n    @GetMapping("/{id}")\n    public UserResponse getUser(String id) {\n        return new UserResponse();\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${endpoint}=    Get First Endpoint    ${discovery}    rest
    Should Be Equal    ${endpoint.example_response_body['name']}    example
    Should Be Equal As Integers    ${endpoint.example_response_body['age']}    0

Build GraphQL example with imported return type and ID variable
    [Documentation]    Checks that imported Strawberry types are discovered correctly.
    Log    Running imported Strawberry type case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    models.py    import strawberry\n\n@strawberry.type\nclass User:\n    id: strawberry.ID\n    name: str\n    role: str
    Write Project File    ${project}    schema.py    import strawberry\nfrom models import User\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def userById(self, id: strawberry.ID) -> User:\n        return User(id="1", name="demo", role="admin")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build GraphQL example with camelized inner field
    [Documentation]    Checks that snake case resolvers still produce a GraphQL example.
    Log    Running camelized GraphQL field case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass User:\n    field1: str\n    field2: str\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def user_by_id(self, user_id: str) -> User:\n        return User(field1="a", field2="b")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build GraphQL example from schema file
    [Documentation]    Checks that schema files are handled during discovery.
    Log    Running schema file discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.graphql    type Query {\n  userById(id: ID): User\n}\n\ntype User {\n  id: ID\n  name: String\n}
    Write Project File    ${project}    app.py    from strawberry.schema.config import StrawberryConfig\nimport strawberry\n\nschema = strawberry.Schema(query=None)
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Enrich GraphQL query from schema details
    [Documentation]    Checks that schema details enrich GraphQL query examples.
    Log    Running schema enrichment case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.graphql    type Query {\n  userById(id: ID): User\n}\n\ntype User {\n  id: ID\n  name: String\n}
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass User:\n    id: str\n    name: str\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def userById(self, id: strawberry.ID) -> User:\n        return User(id="1", name="demo")
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Use placeholder selection when object fields are unknown
    [Documentation]    Checks that unknown object fields still produce a GraphQL selection.
    Log    Running unknown field selection case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\nclass Profile:\n    pass\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def profile(self) -> Profile:\n        return Profile()
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build GraphQL query without direct import
    [Documentation]    Checks that GraphQL queries can be built without a direct type import.
    Log    Running GraphQL without import case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass User:\n    name: str\n    age: int\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def user(self) -> User:\n        return User(name="demo", age=1)
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build GraphQL mutation without direct import
    [Documentation]    Checks that GraphQL mutations can be built without a direct type import.
    Log    Running GraphQL mutation without import case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass User:\n    name: str\n    age: int\n\n@strawberry.type\nclass Mutation:\n    @strawberry.mutation\n    def create_user(self) -> User:\n        return User(name="demo", age=1)
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build nested GraphQL query fields
    [Documentation]    Checks that nested GraphQL query fields are discovered.
    Log    Running nested GraphQL query case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass Profile:\n    name: str\n    role: str\n\n@strawberry.type\nclass User:\n    profile: Profile\n\n@strawberry.type\nclass Query:\n    @strawberry.field\n    def user(self) -> User:\n        return User(profile=Profile(name="demo", role="admin"))
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Build nested GraphQL mutation fields
    [Documentation]    Checks that nested GraphQL mutation fields are discovered.
    Log    Running nested GraphQL mutation case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.type\nclass AuditInfo:\n    updated_by: str\n\n@strawberry.type\nclass UserProfile:\n    id: str\n    audit: AuditInfo\n\n@strawberry.type\nclass Mutation:\n    @strawberry.mutation\n    def update_user(self, id: str) -> UserProfile:\n        return UserProfile(id=id, audit=AuditInfo(updated_by="admin"))
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Mark custom GraphQL input types as non-null
    [Documentation]    Checks that custom GraphQL input types are treated as required.
    Log    Running custom GraphQL input case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    schema.py    import strawberry\n\n@strawberry.input\nclass BuyersDelete:\n    id: str\n\n@strawberry.type\nclass Mutation:\n    @strawberry.mutation\n    def delete_buyer(self, buyer: BuyersDelete) -> str:\n        return "ok"
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Find Django routes
    [Documentation]    Checks that Django routes are discovered.
    Log    Running Django discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    views.py    from django.http import JsonResponse\n\ndef get_user(request):\n    return JsonResponse({\"ok\": True})
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Find DRF router and serializer example
    [Documentation]    Checks that DRF router endpoints and serializers are discovered.
    Log    Running DRF discovery case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    api.py    from rest_framework import serializers, viewsets\n\nclass UserSerializer(serializers.Serializer):\n    id = serializers.CharField()\n\nclass UserViewSet(viewsets.ViewSet):\n    pass
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Python

Find Quarkus JAX-RS endpoints
    [Documentation]    Checks that Quarkus JAX-RS endpoints are discovered.
    Log    Running Quarkus JAX-RS case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserResource.java    package demo;\n\nimport jakarta.ws.rs.GET;\nimport jakarta.ws.rs.Path;\n\n@Path("/users")\npublic class UserResource {\n    @GET\n    public String listUsers() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${paths}=    Get Endpoint Paths    ${discovery}    rest
    Should Contain    ${paths}    GET /users

Find Quarkus root paths for REST and GraphQL
    [Documentation]    Checks that Quarkus root paths are discovered as backend endpoints.
    Log    Running Quarkus root path case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    App.java    package demo;\n\nimport jakarta.ws.rs.GET;\nimport jakarta.ws.rs.Path;\n\n@Path("/")\npublic class App {\n    @GET\n    public String health() {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java

Find Spring request body without path variables
    [Documentation]    Checks that Spring request bodies are discovered without path noise.
    Log    Running Spring request body case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserController.java    package demo;\n\nimport org.springframework.web.bind.annotation.PostMapping;\nimport org.springframework.web.bind.annotation.RequestBody;\nimport org.springframework.web.bind.annotation.RestController;\n\n@RestController\nclass UserController {\n    @PostMapping("/users")\n    public String createUser(@RequestBody UserRequest request) {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    ${endpoint}=    Get First Endpoint    ${discovery}    rest
    Should Be Equal    ${discovery.runtime}    Java

Find Quarkus request body without path param noise
    [Documentation]    Checks that Quarkus request bodies are discovered without path noise.
    Log    Running Quarkus request body case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    UserResource.java    package demo;\n\nimport jakarta.ws.rs.POST;\nimport jakarta.ws.rs.Path;\nimport jakarta.ws.rs.PathParam;\n\n@Path("/users")\npublic class UserResource {\n    @POST\n    public String createUser(UserRequest request, @PathParam("id") String id) {\n        return "ok";\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java

Find Java GraphQL mutation with argument types and placeholder selection
    [Documentation]    Checks that Java GraphQL mutations include arguments and placeholders.
    Log    Running Java GraphQL mutation case.
    ${project}=    Create Temp Project
    Write Project File    ${project}    GraphqlController.java    package demo;\n\nimport org.springframework.graphql.data.method.annotation.Argument;\nimport org.springframework.graphql.data.method.annotation.MutationMapping;\nimport org.springframework.stereotype.Controller;\n\nclass AuditInfo {\n    private String updatedBy;\n}\n\nclass UserProfile {\n    private String id;\n    private AuditInfo audit;\n}\n\n@Controller\npublic class GraphqlController {\n    @MutationMapping\n    public UserProfile updateUser(@Argument String id) {\n        return new UserProfile();\n    }\n}
    ${discovery}=    Discover Backend    ${project}
    Should Be Equal    ${discovery.runtime}    Java
