import textwrap
import unittest

from analyzer.detector_manager import DetectorManager


class JavaDetectorTests(unittest.TestCase):
    def test_detects_spring_endpoint_validation_and_swallowed_exception_risks(self):
        code = textwrap.dedent(
            """
            package demo;

            import org.springframework.web.bind.annotation.PostMapping;
            import org.springframework.web.bind.annotation.RequestBody;
            import org.springframework.web.bind.annotation.RestController;

            @RestController
            public class UserController {
                @PostMapping("/users")
                public String createUser(@RequestBody UserRequest request) {
                    try {
                        return service.create(request);
                    } catch (Exception ex) {
                    }
                }
            }
            """
        )

        issues = DetectorManager().run_all("UserController.java", code)
        titles = {issue.title for issue in issues}

        self.assertTrue(any("accepts input without obvious validation" in title for title in titles))
        self.assertTrue(any("swallows exceptions" in title for title in titles))

    def test_detects_quarkus_n_plus_one_pattern(self):
        code = textwrap.dedent(
            """
            package demo;

            import jakarta.ws.rs.GET;
            import jakarta.ws.rs.Path;

            @Path("/users")
            public class UserResource {
                @GET
                public String listUsers() {
                    for (User user : userRepository.findAll()) {
                        orderRepository.findByUserId(user.id);
                    }
                    return "ok";
                }
            }
            """
        )

        issues = DetectorManager().run_all("UserResource.java", code)
        self.assertTrue(any("N+1 database access" in issue.title for issue in issues))

    def test_detects_java_graphql_query_concatenation(self):
        code = textwrap.dedent(
            """
            package demo;

            import org.springframework.graphql.data.method.annotation.QueryMapping;
            import org.springframework.stereotype.Controller;

            @Controller
            public class SalaryGraphqlController {
                @QueryMapping
                public String calculateSalary(String employeeId) {
                    String query = "SELECT * FROM salary WHERE employee_id = '" + employeeId + "'";
                    return entityManager.createNativeQuery(query).getSingleResult().toString();
                }
            }
            """
        )

        issues = DetectorManager().run_all("SalaryGraphqlController.java", code)
        self.assertTrue(any("Query string concatenation" in issue.title for issue in issues))


if __name__ == "__main__":
    unittest.main()
