# JVM data scouting

Use this reference when the code area is Java, Kotlin, or Groovy on the JVM. Tag notes `data` (for `12-DATABASE.md`) and `features` when a table belongs to a feature. Every note carries `file:line`.

## Schema files

Schema definitions establish baseline tables, relations, and stored logic.

- Search `*.sql` DDL files, Flyway `V*__*.sql` under `db/migration`, and Liquibase changelogs (`databaseChangeLog` in XML, YAML, or JSON).
- Search Flyway repeatable migrations `R__*.sql`; they run again whenever their checksum changes and usually hold views, procedures, and functions. The latest version of each file wins.
- Record each `CREATE TABLE`, key, index, view, procedure, and trigger.
- Resolve migration versions in order; the latest migration wins.

## JPA and Hibernate

ORM mappings define entities, relations, and persistent properties.

- Search `@Entity`, `@Table`, `@Column`, `@Id`, `@OneToMany`, `@ManyToOne`, `@ManyToMany`, and `@JoinColumn`.
- Read `*.hbm.xml` files for `<class table>`, `<property column>`, `<many-to-one>`, and `<set>`.
- Read `persistence.xml` and `hibernate.cfg.xml` for the persistence unit and SQL dialect.
- Map an entity without a `@Table` name to its class name, marked as inference.

## MyBatis

MyBatis mappers define SQL statements and result mappings.

- Read mapper XML files for `<mapper namespace>`, `<select>`, `<insert>`, `<update>`, and `<delete>`.
- Search `@Select`, `@Insert`, `@Update`, and `@Delete` annotations on mapper interfaces.
- Record the tables each statement reads and writes.

## JDBC

Direct JDBC calls execute inline SQL or invoke stored procedures.

- Search `JdbcTemplate`, `NamedParameterJdbcTemplate`, `PreparedStatement`, `createStatement`, and `CallableStatement`.
- Read the SQL string for its tables.
- Record a `CallableStatement` or `{call ...}` as a stored procedure invocation.
- Record SQL built at runtime with its pattern, marked as inference.

## Datasources

Datasource configurations reveal datastore engines and connection sources.

- Read `application.properties` and `application.yml` for `spring.datasource.*` properties.
- Read `context.xml` and `server.xml` for `<Resource>` elements.
- Read `web.xml` for `<resource-ref>` elements and check JNDI lookups.
- Record the datastore engine from the driver class or URL; never record a password or a full URL with credentials.

## Batch and scheduled jobs

Scheduled and batch jobs execute background data access.

- Search `@Scheduled` annotations on methods.
- Search Quartz `Job` classes and read `quartz.properties`.
- Search Spring Batch `Job` and `Step` beans.
- Search cron entries in deployment files.
- Record the tables each job reads and writes.

## Matching

Access matrix cells pair statements and entities with their owning service.

- Record an access-matrix cell from a statement or an entity use in that service: `R` for a read, `W` for a write.
- Place a table in the schema that no code references into `Migration Notes`.
- Place a table written by two services into `Migration Notes`.
