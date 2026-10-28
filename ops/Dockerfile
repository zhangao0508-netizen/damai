FROM eclipse-temurin:17-jre
ARG SERVICE
WORKDIR /app
RUN mkdir -p /app/logs && chown 10001:10001 /app/logs
COPY --chown=10001:10001 damai-server/damai-${SERVICE}-service/target/damai-${SERVICE}-service-0.0.1-SNAPSHOT.jar app.jar
USER 10001:10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
