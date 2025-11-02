# TODO List

## 🎯 High Priority

### Backend Modules
- [ ] **Registry Module**
  - [ ] Member management (CRUD operations)
  - [ ] First-timer registration and tracking
  - [ ] Service attendance records
  - [ ] Departmental assignments
  - [ ] Leadership role assignments
  - [ ] Database models and migrations
  - [ ] API endpoints
  - [ ] Service layer implementation
  - [ ] Tests

- [ ] **Finance Module**
  - [ ] Financial transaction models (offerings, tithes, partnerships)
  - [ ] Partnership arms support (Rhapsody, Healing School, InnerCity Mission, Loveworld TV)
  - [ ] Batch creation and locking
  - [ ] Verification workflows
  - [ ] Reconciliation views
  - [ ] Database models and migrations
  - [ ] API endpoints
  - [ ] Service layer implementation
  - [ ] Tests

- [ ] **Cells Module**
  - [ ] Cell management (CRUD)
  - [ ] Cell leader assignments
  - [ ] Meeting reports
  - [ ] Attendance tracking
  - [ ] Testimony recording
  - [ ] Cell offerings (mirrored to Finance)
  - [ ] Database models and migrations
  - [ ] API endpoints
  - [ ] Service layer implementation
  - [ ] Tests

- [ ] **Reports Module**
  - [ ] Pre-aggregated dashboard data
  - [ ] Materialized views for analytics
  - [ ] Roll-up tables for hierarchical summaries
  - [ ] Report generation (PDF, Excel, CSV)
  - [ ] Export functionality (async via background jobs)
  - [ ] Database models and migrations
  - [ ] API endpoints
  - [ ] Service layer implementation
  - [ ] Tests

- [ ] **Imports/Exports Module**
  - [ ] Legacy data import (CSV, Excel)
  - [ ] Import validation and error handling
  - [ ] Async import processing
  - [ ] Report export generation
  - [ ] Export to S3/MinIO
  - [ ] Export notification (email download link)
  - [ ] Database models and migrations
  - [ ] API endpoints
  - [ ] Service layer implementation
  - [ ] Tests

- [ ] **Audit Module**
  - [ ] Immutable audit log queries
  - [ ] Audit log filtering and search
  - [ ] Audit log retention policies
  - [ ] API endpoints
  - [ ] Tests

### Test Coverage
- [ ] Set up pytest-cov for coverage reporting
- [ ] Configure coverage thresholds
- [ ] Add coverage badge to README
- [ ] Achieve >80% code coverage across all modules
- [ ] Add coverage reporting to CI/CD (when set up)

## 🚧 Medium Priority

### Frontend Development
- [ ] **Next.js Setup**
  - [ ] Initialize Next.js project structure
  - [ ] Configure Tailwind CSS
  - [ ] Set up shadcn/ui components
  - [ ] Configure routing for multi-portal structure
  - [ ] Set up API client library
  - [ ] Authentication flow integration

- [ ] **Registry Portal Frontend**
  - [ ] Member management UI
  - [ ] First-timer registration form
  - [ ] Service attendance forms
  - [ ] Department assignment interface
  - [ ] Leadership role management

- [ ] **Finance Portal Frontend**
  - [ ] Transaction entry forms
  - [ ] Batch management UI
  - [ ] Verification workflows
  - [ ] Reconciliation views
  - [ ] Partnership arm selection

- [ ] **Cells Portal Frontend**
  - [ ] Cell management interface
  - [ ] Meeting report forms
  - [ ] Attendance entry
  - [ ] Testimony submission
  - [ ] Cell offering entry

- [ ] **Reports Portal Frontend**
  - [ ] Dashboard views
  - [ ] Report generation UI
  - [ ] Export options
  - [ ] Filtering and date range selection
  - [ ] Visualization components (charts, graphs)

### Production Infrastructure
- [ ] **Infrastructure as Code**
  - [ ] Choose tooling (Terraform, CloudFormation, Pulumi)
  - [ ] Define infrastructure templates
  - [ ] Set up networking (VPC, subnets, security groups)
  - [ ] Define compute resources (ECS, EKS, or similar)
  - [ ] Set up load balancers
  - [ ] Configure auto-scaling

- [ ] **CI/CD Pipelines**
  - [ ] Set up GitHub Actions / GitLab CI / CircleCI
  - [ ] Configure test pipeline
  - [ ] Configure build pipeline
  - [ ] Configure deployment pipeline
  - [ ] Set up staging environment
  - [ ] Set up production environment
  - [ ] Add automated testing gates

- [ ] **Monitoring & Alerting**
  - [ ] Set up CloudWatch / Datadog / similar
  - [ ] Configure application metrics
  - [ ] Set up log aggregation
  - [ ] Configure alerting rules
  - [ ] Set up uptime monitoring
  - [ ] Create runbooks

- [ ] **Secrets Management**
  - [ ] Integrate AWS Secrets Manager / HashiCorp Vault
  - [ ] Rotate secrets automatically
  - [ ] Secure credential storage
  - [ ] Remove hardcoded secrets from code

- [ ] **High Availability Setup**
  - [ ] Multi-AZ deployment
  - [ ] Database replication
  - [ ] Redis cluster setup
  - [ ] Load balancer health checks
  - [ ] Disaster recovery plan

## 📋 Low Priority / Future Enhancements

### Backend Improvements
- [ ] Add API rate limiting configuration UI
- [ ] Implement caching layer (Redis) for frequently accessed data
- [ ] Add GraphQL API option
- [ ] Implement API versioning strategy
- [ ] Add request/response compression optimization
- [ ] Implement database query optimization and indexing review
- [ ] Add database backup automation
- [ ] Implement data archival strategy

### Observability Enhancements
- [ ] Add distributed tracing (OpenTelemetry integration)
- [ ] Enhance error tracking with stack traces
- [ ] Add custom business metrics dashboards
- [ ] Implement log retention policies
- [ ] Add performance profiling tools

### Developer Experience
- [ ] Add pre-commit hooks (black, linting, tests)
- [ ] Set up development environment documentation
- [ ] Add API documentation generation
- [ ] Create developer onboarding guide
- [ ] Add code review guidelines

### Security Enhancements
- [ ] Implement CSRF protection
- [ ] Add API key authentication for service accounts
- [ ] Implement IP whitelisting
- [ ] Add security scanning to CI/CD
- [ ] Regular dependency updates and security patches
- [ ] Penetration testing

### Documentation
- [ ] API documentation site (Swagger UI or similar)
- [ ] Architecture diagrams
- [ ] Database schema documentation
- [ ] Deployment runbooks
- [ ] Troubleshooting guide
- [ ] User guides for each portal

## 🔄 Maintenance

### Ongoing Tasks
- [ ] Regular dependency updates
- [ ] Security patches
- [ ] Performance monitoring and optimization
- [ ] Database index optimization
- [ ] Code cleanup and refactoring
- [ ] Test maintenance and expansion

## 📝 Notes

- Prioritize backend modules first to establish core functionality
- Frontend can be developed in parallel once backend APIs are stable
- Production infrastructure can be planned alongside development but implemented later
- Test coverage should be maintained as features are added

