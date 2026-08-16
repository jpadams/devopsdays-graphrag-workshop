// == DevOpsDays Portland: the microservices knowledge graph ====================
//
// One graph holding BOTH kinds of data:
//   structured   -- which service depends on which, who maintains what
//   unstructured -- the prose in Task.description, which we embed in step 02
//
// That combination is the whole point. A vector store could hold the prose but
// not the topology; a relational DB could hold the topology but answers
// "how will the recommendation service be updated?" badly. Here they are one
// query away from each other.
//
// Adapted from Tomaz Bratanic's DevOps RAG blog post. Vendored deliberately:
// the original fetched this from a GitHub gist at runtime, which is one more
// thing to fail on conference wifi.
//
// Idempotent -- safe to re-run.
//
// NOTE: this file is ONE Cypher statement. There are no semicolons on purpose --
// the relationship MERGEs at the bottom reference variables (catalog, order, ...)
// bound by the node MERGEs at the top, and those bindings do not survive a
// statement boundary. Send the whole file in one go. `make load` does this.

// -- Microservices -----------------------------------------------
// The architecture. `technology` gives text2cypher something
// to filter on that is not just a name.
MERGE (catalog:Microservice {name: 'CatalogService', technology: 'Java'})
MERGE (order:Microservice {name: 'OrderService', technology: 'Python'})
MERGE (user:Microservice {name: 'UserService', technology: 'Go'})
MERGE (payment:Microservice {name: 'PaymentService', technology: 'Node.js'})
MERGE (inventory:Microservice {name: 'InventoryService', technology: 'Java'})
MERGE (shipping:Microservice {name: 'ShippingService', technology: 'Python'})
MERGE (review:Microservice {name: 'ReviewService', technology: 'Go'})
MERGE (recommendation:Microservice {name: 'RecommendationService', technology: 'Node.js'})
MERGE (auth:Microservice {name: 'AuthService', technology: 'Node.js'})
MERGE (db:Microservice {name: 'Database', technology: 'SQL'})
MERGE (cache:Microservice {name: 'Cache', technology: 'In-memory'})
MERGE (mq:Microservice {name: 'MessageQueue', technology: 'Pub-Sub'})
MERGE (api:Microservice {name: 'ExternalAPI', technology: 'REST'})

// -- Tasks -------------------------------------------------------
// The unstructured half. `description` is what we embed.
// Note: two tasks are both named "Optimize" -- name is NOT a unique key here.
// Keep that in mind in step 02 when we pick what to MERGE on.
MERGE (bugFixCatalog:Task {name: 'BugFix', description: 'Address and resolve a critical bug impacting the CatalogService, affecting the user interface and experience, and hampering the overall performance and responsiveness of the service.', status: 'open'})
MERGE (featureAddOrder:Task {name: 'FeatureAdd', description: 'Implement a new feature in OrderService to facilitate bulk orders, ensuring the features seamless integration with existing functionalities and maintaining the overall stability and performance of the service.', status: 'in progress'})
MERGE (refactorUser:Task {name: 'Refactor', description: 'Refactor the UserService codebase to enhance its readability, maintainability, and scalability, focusing primarily on modularization and optimization of existing functionalities.', status: 'completed'})
MERGE (optimizePayment:Task {name: 'Optimize', description: 'Optimize PaymentService by refining the transaction processing logic, reducing the service’s latency, and improving its reliability and efficiency in handling transactions.', status: 'open'})
MERGE (updateInventory:Task {name: 'Update', description: 'Update InventoryService to include real-time stock updates, ensuring accurate reflection of the inventory levels and aiding in the efficient management of stock.', status: 'in progress'})
MERGE (enhanceShipping:Task {name: 'Enhance', description: 'Enhance the ShippingService by integrating a new shipping partner API, thereby expanding the shipping options available to the customers and improving the overall delivery experience.', status: 'completed'})
MERGE (reviewFix:Task {name: 'ReviewFix', description: 'Rectify a recurring issue in ReviewService affecting the retrieval of user reviews, by refining the service’s logic and improving its efficiency in handling and displaying user reviews.', status: 'open'})
MERGE (recommendationFeature:Task {name: 'RecommendationFeature', description: 'Add a new feature to RecommendationService to provide more personalized and accurate product recommendations to the users, leveraging user behavior and preference data.', status: 'in progress'})
MERGE (optimizeAuth:Task {name: 'Optimize', description: 'Enhance AuthService’s performance and security by optimizing the authentication mechanisms and implementing additional security measures to safeguard user information.', status: 'open'})
MERGE (newTask:Task {name: 'ImproveSecurity', description: 'Enhance the security of microservices by implementing advanced encryption and securing endpoints.', status: 'open'})

// -- Teams -------------------------------------------------------
// Renamed from the source dataset's TeamA/B/C/D, which nobody can hold in their
// head for two hours. Each name describes what the team actually owns:
//
//   Platform     Catalog, Inventory, Auth        the services others build on
//   Fulfillment  Order, Shipping                 getting the order out the door
//   Accounts     User, Review                    who the customer is, what they say
//   Revenue      Payment, Recommendation         the money, and what drives it
//
// This also makes the demos honest in a way letters do not: "who owns the
// authentication work" has a real answer you can sanity-check by eye, and when
// the agent claims PaymentService belongs to Fulfillment you will notice,
// because fulfilment teams do not own payments.
MERGE (platform:Team {name: 'Platform'})
MERGE (fulfillment:Team {name: 'Fulfillment'})
MERGE (accounts:Team {name: 'Accounts'})
MERGE (revenue:Team {name: 'Revenue'})

// -- People ------------------------------------------------------
MERGE (alice:Person {name: 'Alice'})
MERGE (bob:Person {name: 'Bob'})
MERGE (charlie:Person {name: 'Charlie'})
MERGE (diana:Person {name: 'Diana'})
MERGE (eva:Person {name: 'Eva'})
MERGE (frank:Person {name: 'Frank'})

// -- :DEPENDS_ON -------------------------------------------------
// The dependency graph. This is what makes "which services depend on
// Database indirectly?" a *graph* question -- variable-length traversal.
MERGE (catalog)-[:DEPENDS_ON]->(db)
MERGE (order)-[:DEPENDS_ON]->(db)
MERGE (user)-[:DEPENDS_ON]->(db)
MERGE (payment)-[:DEPENDS_ON]->(db)
MERGE (inventory)-[:DEPENDS_ON]->(db)
MERGE (shipping)-[:DEPENDS_ON]->(mq)
MERGE (review)-[:DEPENDS_ON]->(cache)
MERGE (recommendation)-[:DEPENDS_ON]->(api)
MERGE (auth)-[:DEPENDS_ON]->(db)
MERGE (order)-[:DEPENDS_ON]->(inventory)
MERGE (order)-[:DEPENDS_ON]->(shipping)
MERGE (order)-[:DEPENDS_ON]->(payment)
MERGE (catalog)-[:DEPENDS_ON]->(review)
MERGE (catalog)-[:DEPENDS_ON]->(recommendation)
MERGE (user)-[:DEPENDS_ON]->(auth)
MERGE (payment)-[:DEPENDS_ON]->(auth)
MERGE (shipping)-[:DEPENDS_ON]->(auth)

// -- :MAINTAINED_BY ----------------------------------------------
// Ownership. Note Database, Cache, MessageQueue and ExternalAPI have NO
// owning team -- a deliberate gap, and a good question to ask the agent.
MERGE (catalog)-[:MAINTAINED_BY]->(platform)
MERGE (order)-[:MAINTAINED_BY]->(fulfillment)
MERGE (user)-[:MAINTAINED_BY]->(accounts)
MERGE (payment)-[:MAINTAINED_BY]->(revenue)
MERGE (inventory)-[:MAINTAINED_BY]->(platform)
MERGE (shipping)-[:MAINTAINED_BY]->(fulfillment)
MERGE (review)-[:MAINTAINED_BY]->(accounts)
MERGE (recommendation)-[:MAINTAINED_BY]->(revenue)
MERGE (auth)-[:MAINTAINED_BY]->(platform)

// -- :ASSIGNED_TO ------------------------------------------------
// Work assignment.
MERGE (bugFixCatalog)-[:ASSIGNED_TO]->(platform)
MERGE (featureAddOrder)-[:ASSIGNED_TO]->(fulfillment)
MERGE (refactorUser)-[:ASSIGNED_TO]->(accounts)
MERGE (optimizePayment)-[:ASSIGNED_TO]->(revenue)
MERGE (updateInventory)-[:ASSIGNED_TO]->(platform)
MERGE (enhanceShipping)-[:ASSIGNED_TO]->(fulfillment)
MERGE (reviewFix)-[:ASSIGNED_TO]->(accounts)
MERGE (recommendationFeature)-[:ASSIGNED_TO]->(revenue)
MERGE (optimizeAuth)-[:ASSIGNED_TO]->(platform)
MERGE (newTask)-[:ASSIGNED_TO]->(platform)

// -- :LINKED_TO --------------------------------------------------
// Ties each task back to the service it touches -- the bridge between the
// unstructured half and the structured half.
MERGE (bugFixCatalog)-[:LINKED_TO]->(catalog)
MERGE (featureAddOrder)-[:LINKED_TO]->(order)
MERGE (refactorUser)-[:LINKED_TO]->(user)
MERGE (optimizePayment)-[:LINKED_TO]->(payment)
MERGE (updateInventory)-[:LINKED_TO]->(inventory)
MERGE (enhanceShipping)-[:LINKED_TO]->(shipping)
MERGE (reviewFix)-[:LINKED_TO]->(review)
MERGE (recommendationFeature)-[:LINKED_TO]->(recommendation)
MERGE (optimizeAuth)-[:LINKED_TO]->(auth)
MERGE (newTask)-[:LINKED_TO]->(auth)

// -- :PART_OF ----------------------------------------------------
// Team membership.
MERGE (alice)-[:PART_OF]->(platform)
MERGE (bob)-[:PART_OF]->(fulfillment)
MERGE (charlie)-[:PART_OF]->(accounts)
MERGE (diana)-[:PART_OF]->(revenue)
MERGE (eva)-[:PART_OF]->(platform)
MERGE (frank)-[:PART_OF]->(fulfillment)
