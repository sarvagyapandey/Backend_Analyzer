*** Settings ***
Library    robot_tests/BackendAnalyzerLibrary.py

*** Test Cases ***
Find Spring controller validation and swallowed errors
    [Documentation]    Checks that Spring controller validation gaps and swallowed exceptions are detected.
    Log    Running Spring controller detector case.
    ${code}=    Catenate    SEPARATOR=\n    package demo;    import org.springframework.web.bind.annotation.PostMapping;    import org.springframework.web.bind.annotation.RequestBody;    import org.springframework.web.bind.annotation.RestController;    @RestController    public class UserController {    @PostMapping("/users")    public String createUser(@RequestBody UserRequest request) {    try {    return service.create(request);    } catch (Exception ex) {    }    }    }
    ${issues}=    Analyze Java Code    ${code}    UserController.java
    Issue Titles Should Contain    ${issues}    accepts input without obvious validation
    Issue Titles Should Contain    ${issues}    swallows exceptions
    Log    Passed because the Java controller contains validation and exception-handling risks.

Find Quarkus N plus one pattern
    [Documentation]    Checks that a Quarkus loop with repeated data access is reported as an N+1 risk.
    Log    Running Quarkus N+1 detector case.
    ${code}=    Catenate    SEPARATOR=\n    package demo;    import jakarta.ws.rs.GET;    import jakarta.ws.rs.Path;    @Path("/users")    public class UserResource {    @GET    public String listUsers() {    for (User user : userRepository.findAll()) {    orderRepository.findByUserId(user.id);    }    return "ok";    }    }
    ${issues}=    Analyze Java Code    ${code}    UserResource.java
    Issue Titles Should Contain    ${issues}    N+1 database access
    Log    Passed because repeated database access was detected inside a loop.

Find Java GraphQL query concatenation
    [Documentation]    Checks that string concatenation inside a GraphQL query is flagged.
    Log    Running Java GraphQL injection detector case.
    ${code}=    Catenate    SEPARATOR=\n    package demo;    import org.springframework.graphql.data.method.annotation.QueryMapping;    import org.springframework.stereotype.Controller;    @Controller    public class SalaryGraphqlController {    @QueryMapping    public String calculateSalary(String employeeId) {    String query = "SELECT * FROM salary WHERE employee_id = '" + employeeId + "'";    return entityManager.createNativeQuery(query).getSingleResult().toString();    }    }
    ${issues}=    Analyze Java Code    ${code}    SalaryGraphqlController.java
    Issue Titles Should Contain    ${issues}    Query string concatenation
    Log    Passed because the GraphQL query is built by string concatenation.
