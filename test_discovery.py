import tempfile
import textwrap
import unittest
from pathlib import Path

from analyzer.discovery import BackendDiscoveryEngine


class DiscoveryEngineTests(unittest.TestCase):
    def test_discovers_fastapi_rest_endpoint_and_payload_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "app.py").write_text(
                textwrap.dedent(
                    """
                    from fastapi import FastAPI
                    from pydantic import BaseModel

                    app = FastAPI()

                    class UserCreate(BaseModel):
                        name: str
                        age: int
                        active: bool

                    @app.post("/users")
                    async def create_user(payload: UserCreate):
                        return payload
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            self.assertEqual(discovery.runtime, "Python")
            self.assertEqual(discovery.api_style, "REST")
            self.assertIn("FastAPI", discovery.frameworks)
            self.assertEqual(len(discovery.endpoints), 1)
            endpoint = discovery.endpoints[0]
            self.assertEqual(endpoint.method, "POST")
            self.assertEqual(endpoint.path, "/users")
            self.assertEqual(
                endpoint.example_json_body,
                {"name": "example", "age": 0, "active": False},
            )

    def test_discovers_spring_rest_and_graphql_endpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "UserController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.web.bind.annotation.GetMapping;
                    import org.springframework.web.bind.annotation.RequestMapping;
                    import org.springframework.web.bind.annotation.RestController;
                    import org.springframework.graphql.data.method.annotation.QueryMapping;

                    @RestController
                    @RequestMapping("/api/users")
                    public class UserController {
                        @GetMapping("/{id}")
                        public String getUser() {
                            return "ok";
                        }

                        @QueryMapping
                        public String userProfile() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            self.assertEqual(discovery.runtime, "Java")
            self.assertEqual(discovery.api_style, "REST + GraphQL")
            self.assertIn("Spring Web", discovery.frameworks)
            self.assertIn("Spring GraphQL", discovery.frameworks)
            rest_paths = {(endpoint.method, endpoint.path) for endpoint in discovery.endpoints if endpoint.kind == "rest"}
            graphql_names = {endpoint.name for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn(("GET", "/api/users/{id}"), rest_paths)
            self.assertIn("userProfile", graphql_names)

    def test_discovers_explicit_spring_graphql_mapping_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "GraphqlController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.graphql.data.method.annotation.QueryMapping;
                    import org.springframework.stereotype.Controller;

                    @Controller
                    public class GraphqlController {
                        @QueryMapping(name = "keycloakgraphql")
                        public String graphql() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_names = {endpoint.name for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn("keycloakgraphql", graphql_names)

    def test_discovers_custom_spring_graphql_http_path_from_properties(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "application.properties").write_text(
                "spring.graphql.path=/keycloakgraphql\n",
                encoding="utf-8",
            )
            (project / "GraphqlController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.graphql.data.method.annotation.QueryMapping;
                    import org.springframework.stereotype.Controller;

                    @Controller
                    public class GraphqlController {
                        @QueryMapping
                        public String userProfile() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_paths = {endpoint.path for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn("/keycloakgraphql", graphql_paths)

    def test_discovers_spring_context_path_for_rest_and_graphql(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "application.properties").write_text(
                "server.servlet.context-path=/api\nspring.graphql.path=/graphql\n",
                encoding="utf-8",
            )
            (project / "UserController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.graphql.data.method.annotation.QueryMapping;
                    import org.springframework.stereotype.Controller;
                    import org.springframework.web.bind.annotation.GetMapping;
                    import org.springframework.web.bind.annotation.RequestMapping;
                    import org.springframework.web.bind.annotation.RestController;

                    @RestController
                    @RequestMapping("/users")
                    class UserController {
                        @GetMapping("/{id}")
                        public String getUser() {
                            return "ok";
                        }
                    }

                    @Controller
                    class GraphqlController {
                        @QueryMapping
                        public String userProfile() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            rest_paths = {(endpoint.method, endpoint.path) for endpoint in discovery.endpoints if endpoint.kind == "rest"}
            graphql_paths = {endpoint.path for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn(("GET", "/api/users/{id}"), rest_paths)
            self.assertIn("/api/graphql", graphql_paths)

    def test_discovers_custom_python_graphql_mount_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "app.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry
                    from fastapi import FastAPI
                    from strawberry.fastapi import GraphQLRouter

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userProfile(self) -> str:
                            return "ok"

                    schema = strawberry.Schema(query=Query)
                    graphql_app = GraphQLRouter(schema)

                    app = FastAPI()
                    app.mount("/keycloakgraphql", graphql_app)
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_paths = {endpoint.path for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            graphql_names = {endpoint.name for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn("/keycloakgraphql", graphql_paths)
            self.assertIn("userProfile", graphql_names)

    def test_discovers_custom_fastapi_graphql_router_wrapper_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "main.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry
                    from fastapi import FastAPI

                    class OrjsonGraphQLRouter:
                        def __init__(self, schema, context_getter=None):
                            self.schema = schema
                            self.context_getter = context_getter

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def health(self) -> str:
                            return "ok"

                    schema = strawberry.Schema(query=Query)
                    graphql_app = OrjsonGraphQLRouter(schema)

                    app = FastAPI()
                    app.include_router(graphql_app, prefix="/keycloakgraphql")
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_paths = {endpoint.path for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn("/keycloakgraphql", graphql_paths)

    def test_builds_graphql_example_with_placeholder_fields_for_strawberry_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class User:
                        id: str
                        username: str
                        email: str

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, user_id: str) -> User:
                            return User(id="1", username="demo", email="demo@example.com")
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("query userByIdQuery($user_id: String!)", graphql_endpoint.graphql_query)
            self.assertIn("userById(user_id: $user_id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)
            self.assertEqual(graphql_endpoint.graphql_variables, {"user_id": "example"})

    def test_discovers_java_graphql_variables_and_placeholder_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "GraphqlController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.graphql.data.method.annotation.QueryMapping;
                    import org.springframework.stereotype.Controller;

                    class UserProfile {
                        private String name;
                        private Integer age;
                    }

                    @Controller
                    public class GraphqlController {
                        @QueryMapping
                        public UserProfile userById(String userId) {
                            return new UserProfile();
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("userById(userId: $userId) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)
            self.assertEqual(graphql_endpoint.graphql_variables, {"userId": "example"})

    def test_discovers_java_rest_response_example_from_return_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "UserController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.web.bind.annotation.GetMapping;
                    import org.springframework.web.bind.annotation.RequestMapping;
                    import org.springframework.web.bind.annotation.RestController;

                    class UserResponse {
                        private String name;
                        private Integer age;
                    }

                    @RestController
                    @RequestMapping("/users")
                    public class UserController {
                        @GetMapping("/{id}")
                        public UserResponse getUser(String id) {
                            return new UserResponse();
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            rest_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "rest")
            self.assertEqual(rest_endpoint.example_response_body, {"name": "example", "age": 0})

    def test_builds_graphql_example_with_imported_return_type_and_id_variable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "models.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class User:
                        id: strawberry.ID
                        name: str
                        role: str
                    """
                ),
                encoding="utf-8",
            )
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry
                    from models import User

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, id: strawberry.ID) -> User:
                            return User(id="1", name="demo", role="admin")
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("query userByIdQuery($id: ID!)", graphql_endpoint.graphql_query)
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)
            self.assertEqual(graphql_endpoint.graphql_variables, {"id": "example-id"})

    def test_builds_graphql_example_from_schema_file_with_placeholder_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "schema.graphql").write_text(
                textwrap.dedent(
                    """
                    type Query {
                      userById(id: ID): User
                    }

                    type User {
                      id: ID
                      name: String
                      className: String
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertEqual(graphql_endpoint.name, "userById")
            self.assertIn("query userByIdQuery($id: ID)", graphql_endpoint.graphql_query)
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)
            self.assertEqual(graphql_endpoint.graphql_variables, {"id": "example-id"})

    def test_schema_enriches_code_discovered_graphql_query_with_placeholder_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "schema.graphqls").write_text(
                textwrap.dedent(
                    """
                    type Query {
                      userById(id: ID!): User
                    }

                    type User {
                      id: ID!
                      username: String
                      email: String
                    }
                    """
                ),
                encoding="utf-8",
            )
            (project / "resolver.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, id: strawberry.ID):
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_graphql_query_uses_placeholder_selection_when_object_fields_are_unknown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, id: strawberry.ID) -> User:
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("query userByIdQuery($id: ID!)", graphql_endpoint.graphql_query)
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_graphql_query_uses_placeholder_fields_without_direct_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "models.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class User:
                        id: strawberry.ID
                        username: str
                        email: str
                    """
                ),
                encoding="utf-8",
            )
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, id: strawberry.ID) -> User:
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("query userByIdQuery($id: ID!)", graphql_endpoint.graphql_query)
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_graphql_mutation_uses_placeholder_fields_without_direct_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "models.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class User:
                        id: strawberry.ID
                        username: str
                        email: str
                    """
                ),
                encoding="utf-8",
            )
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Mutation:
                        @strawberry.mutation
                        def updateUser(self, id: strawberry.ID, username: str) -> User:
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("mutation updateUserOperation($id: ID!, $username: String!)", graphql_endpoint.graphql_query)
            self.assertIn("updateUser(id: $id, username: $username) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_graphql_query_uses_placeholder_fields_for_nested_project_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "models.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Address:
                        city: str
                        country: str

                    @strawberry.type
                    class Profile:
                        bio: str
                        address: Address

                    @strawberry.type
                    class User:
                        id: strawberry.ID
                        profile: Profile
                    """
                ),
                encoding="utf-8",
            )
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Query:
                        @strawberry.field
                        def userById(self, id: strawberry.ID) -> User:
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("userById(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_graphql_mutation_uses_placeholder_fields_for_nested_project_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "models.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class AuditInfo:
                        updatedBy: str
                        updatedAt: str

                    @strawberry.type
                    class User:
                        id: strawberry.ID
                        audit: AuditInfo
                    """
                ),
                encoding="utf-8",
            )
            (project / "schema.py").write_text(
                textwrap.dedent(
                    """
                    import strawberry

                    @strawberry.type
                    class Mutation:
                        @strawberry.mutation
                        def updateUser(self, id: strawberry.ID) -> User:
                            return None
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            graphql_endpoint = next(endpoint for endpoint in discovery.endpoints if endpoint.kind == "graphql")
            self.assertIn("mutation updateUserOperation($id: ID!)", graphql_endpoint.graphql_query)
            self.assertIn("updateUser(id: $id) {", graphql_endpoint.graphql_query)
            self.assertIn("field1", graphql_endpoint.graphql_query)
            self.assertIn("field2", graphql_endpoint.graphql_query)

    def test_discovers_django_function_and_class_based_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "views.py").write_text(
                textwrap.dedent(
                    """
                    from rest_framework.decorators import api_view
                    from rest_framework.views import APIView

                    @api_view(["GET", "POST"])
                    def users(request):
                        return None

                    class UserDetailView(APIView):
                        def get(self, request, user_id):
                            return None

                        def delete(self, request, user_id):
                            return None
                    """
                ),
                encoding="utf-8",
            )
            (project / "urls.py").write_text(
                textwrap.dedent(
                    """
                    from django.urls import path
                    from views import users, UserDetailView

                    urlpatterns = [
                        path("users/", users),
                        path("users/<int:user_id>/", UserDetailView.as_view()),
                    ]
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            endpoints = {(endpoint.method, endpoint.path) for endpoint in discovery.endpoints if endpoint.kind == "rest"}
            self.assertIn(("GET", "/users/"), endpoints)
            self.assertIn(("POST", "/users/"), endpoints)
            self.assertIn(("GET", "/users/{user_id}/"), endpoints)
            self.assertIn(("DELETE", "/users/{user_id}/"), endpoints)

    def test_discovers_drf_router_endpoints_and_serializer_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "views.py").write_text(
                textwrap.dedent(
                    """
                    from rest_framework import routers, serializers, viewsets

                    class UserSerializer(serializers.Serializer):
                        name = serializers.CharField()
                        age = serializers.IntegerField()

                    class UserViewSet(viewsets.ModelViewSet):
                        serializer_class = UserSerializer

                    router = routers.DefaultRouter()
                    router.register("users", UserViewSet)
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            endpoints = {
                (endpoint.method, endpoint.path): endpoint.example_json_body
                for endpoint in discovery.endpoints
                if endpoint.kind == "rest"
            }
            self.assertIn(("GET", "/users"), endpoints)
            self.assertIn(("POST", "/users"), endpoints)
            self.assertIn(("PATCH", "/users/{id}"), endpoints)
            self.assertEqual(endpoints[("POST", "/users")], {"name": "example", "age": 0})

    def test_discovers_quarkus_jaxrs_endpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "GreetingResource.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import io.quarkus.runtime.Startup;
                    import jakarta.ws.rs.GET;
                    import jakarta.ws.rs.POST;
                    import jakarta.ws.rs.Path;

                    @Startup
                    @Path("/greetings")
                    public class GreetingResource {
                        @GET
                        public String list() {
                            return "ok";
                        }

                        @POST
                        @Path("/create")
                        public String create() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            self.assertIn("Quarkus", discovery.frameworks)
            endpoints = {(endpoint.method, endpoint.path) for endpoint in discovery.endpoints if endpoint.kind == "rest"}
            self.assertIn(("GET", "/greetings"), endpoints)
            self.assertIn(("POST", "/greetings/create"), endpoints)

    def test_discovers_quarkus_root_paths_for_rest_and_graphql(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "application.properties").write_text(
                "quarkus.http.root-path=/service\nquarkus.smallrye-graphql.root-path=/graphql-ui\n",
                encoding="utf-8",
            )
            (project / "GreetingResource.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import jakarta.ws.rs.GET;
                    import jakarta.ws.rs.Path;
                    import org.eclipse.microprofile.graphql.GraphQLApi;
                    import org.eclipse.microprofile.graphql.Query;

                    @Path("/greetings")
                    public class GreetingResource {
                        @GET
                        public String list() {
                            return "ok";
                        }
                    }

                    @GraphQLApi
                    class GreetingGraphql {
                        @Query
                        public String greeting() {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            rest_paths = {(endpoint.method, endpoint.path) for endpoint in discovery.endpoints if endpoint.kind == "rest"}
            graphql_paths = {endpoint.path for endpoint in discovery.endpoints if endpoint.kind == "graphql"}
            self.assertIn(("GET", "/service/greetings"), rest_paths)
            self.assertIn("/service/graphql-ui", graphql_paths)

    def test_discovers_spring_request_body_payload_without_including_path_variables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "UserController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.web.bind.annotation.PathVariable;
                    import org.springframework.web.bind.annotation.PostMapping;
                    import org.springframework.web.bind.annotation.RequestBody;
                    import org.springframework.web.bind.annotation.RequestMapping;
                    import org.springframework.web.bind.annotation.RestController;

                    class UserCreateRequest {
                        private String username;
                        private Integer age;
                    }

                    @RestController
                    @RequestMapping("/users")
                    public class UserController {
                        @PostMapping("/{tenantId}")
                        public String createUser(@PathVariable String tenantId, @RequestBody UserCreateRequest request) {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            endpoint = next(item for item in discovery.endpoints if item.kind == "rest")
            self.assertEqual(endpoint.path, "/users/{tenantId}")
            self.assertEqual(endpoint.example_json_body, {"username": "example", "age": 0})

    def test_discovers_quarkus_request_body_payload_without_path_param_noise(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "GreetingResource.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import jakarta.ws.rs.POST;
                    import jakarta.ws.rs.PUT;
                    import jakarta.ws.rs.Path;
                    import jakarta.ws.rs.PathParam;

                    class GreetingRequest {
                        private String message;
                        private Boolean enabled;
                    }

                    @Path("/greetings")
                    public class GreetingResource {
                        @PUT
                        @Path("/{id}")
                        public String update(@PathParam("id") String id, GreetingRequest request) {
                            return "ok";
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            endpoint = next(item for item in discovery.endpoints if item.kind == "rest")
            self.assertEqual(endpoint.example_json_body, {"message": "example", "enabled": False})

    def test_discovers_java_graphql_mutation_with_argument_types_and_placeholder_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "GraphqlController.java").write_text(
                textwrap.dedent(
                    """
                    package demo;

                    import org.springframework.graphql.data.method.annotation.Argument;
                    import org.springframework.graphql.data.method.annotation.MutationMapping;
                    import org.springframework.stereotype.Controller;

                    class AuditInfo {
                        private String updatedBy;
                    }

                    class UserProfile {
                        private String id;
                        private AuditInfo audit;
                    }

                    @Controller
                    public class GraphqlController {
                        @MutationMapping
                        public UserProfile updateUser(@Argument String id) {
                            return new UserProfile();
                        }
                    }
                    """
                ),
                encoding="utf-8",
            )

            discovery = BackendDiscoveryEngine().discover(str(project))

            endpoint = next(item for item in discovery.endpoints if item.kind == "graphql")
            self.assertIn("mutation updateUserOperation($id: String!)", endpoint.graphql_query)
            self.assertIn("updateUser(id: $id) {", endpoint.graphql_query)
            self.assertIn("field1", endpoint.graphql_query)
            self.assertIn("field2", endpoint.graphql_query)
            self.assertEqual(endpoint.graphql_variables, {"id": "example"})


if __name__ == "__main__":
    unittest.main()
